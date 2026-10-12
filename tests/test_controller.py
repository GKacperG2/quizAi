import time
from threading import Event
import pytest
from quiz_assistant.controller import SessionController
from quiz_assistant.ai.provider import OpenAIProvider, ProviderError, ProviderErrorKind, AnalysisResult, UsageSummary
from quiz_assistant.ai.schemas import QuizAnswer
from quiz_assistant.models import AppState, ApiConfig, CaptureRegion, MonitorDescriptor
from helpers import FakeFactory, frame, answer_payload


class FakeOverlay:
    def __init__(self):
        self.visible = False
        self.results = []
        self.errors = []
    def clear(self):
        self.visible = False
        self.results.clear()
    def toggle(self):
        self.visible = not self.visible
    def show_loading(self, *args):
        self.visible = True
    def show_analysis_result(self, *args):
        self.visible = True
        self.results.append(args)
    def update_progress(self, *args):
        pass
    def show_error(self, message):
        self.visible = True
        self.errors.append(message)


class FakeCapture:
    def __init__(self):
        self.calls = 0
        self.delay = 0
        self.failure = False
    def capture(self, region, monitor):
        self.calls += 1
        time.sleep(self.delay)
        if self.failure:
            raise RuntimeError("private screenshot content must never be shown")
        return frame(self.calls)


def pump(app, until, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if until():
            return
        time.sleep(.005)
    assert until(), "Qt operation did not finish"


@pytest.fixture
def setup_controller(monkeypatch, qt_app):
    from quiz_assistant import controller as module
    monkeypatch.setattr(module, "flush_compositor", lambda: True)
    overlay, capture, factory = FakeOverlay(), FakeCapture(), FakeFactory()
    provider = OpenAIProvider(factory)
    provider.configure("offline-fake", ApiConfig())
    controller = SessionController(overlay, capture)
    monitor = MonitorDescriptor("D1", "test", 1, 0, 0, 1920, 1080, 0, 0, 1920, 1080, 1.0, 96)
    region = CaptureRegion("D1", 0, 0, 1000, 800, 96, 1920, 1080)
    controller.configure_environment([monitor], region)
    controller.set_hotkeys_ready(True)
    controller.set_api_provider(provider, ApiConfig())
    yield controller, overlay, capture, factory
    controller.shutdown()
    pump(qt_app, lambda: not controller.busy)


def test_state_and_pause(setup_controller):
    controller, _, _, _ = setup_controller
    assert controller.state is AppState.READY
    controller.set_ready_enabled(False)
    assert controller.state is AppState.PAUSED
    controller.analyze()
    assert not controller.busy
    controller.set_ready_enabled(True)
    assert controller.state is AppState.READY
    controller.set_hotkeys_ready(False, "Conflict")
    assert controller.state is AppState.UNCONFIGURED


def test_vertical_flow_once_no_freshness_recapture(setup_controller, qt_app):
    c, overlay, capture, factory = setup_controller
    c.analyze()
    generation = c.generation_id
    for _ in range(20):
        c.analyze()
    assert c.generation_id == generation
    pump(qt_app, lambda: not c.busy)
    assert capture.calls == 1  # No current-screen/freshness capture at all.
    assert len(factory.client.payloads) == 1
    assert len(overlay.results) == 1
    assert c.state is AppState.SHOWING_RESULT
    assert c.budget_snapshot.spent_usd == pytest.approx(.011)


def test_timer_hover_scroll_cannot_reject_saved_snapshot(setup_controller, qt_app):
    c, overlay, capture, factory = setup_controller
    c.add_frame()
    pump(qt_app, lambda: not c.busy)
    captured = c.frames[0]
    # Current screen can become wholly different; batch analysis must not capture again.
    capture.failure = True
    c.analyze()
    pump(qt_app, lambda: not c.busy)
    assert overlay.results[0][2] == (captured,)
    assert capture.calls == 1


def test_batch_six_limit_reorder_delete_clear(setup_controller, qt_app):
    c, _, capture, _ = setup_controller
    for _ in range(6):
        c.add_frame()
        pump(qt_app, lambda: not c.busy)
    original = c.frames
    c.add_frame()
    assert len(c.frames) == 6 and capture.calls == 6
    c.move_frame(0, 1)
    assert c.frames[1] == original[0]
    c.remove_frame(1)
    assert len(c.frames) == 5
    c.cancel()
    assert c.frames == ()


@pytest.mark.parametrize("stage", ["scheduled", "capture", "api"])
def test_cancel_at_every_stage_no_late_overlay(setup_controller, qt_app, stage):
    c, overlay, capture, factory = setup_controller
    capture.delay = .05
    factory.client.delay = .2
    c.analyze()
    if stage == "capture":
        pump(qt_app, lambda: capture.calls == 1)
    elif stage == "api":
        pump(qt_app, lambda: bool(factory.client.payloads))
    c.cancel()
    assert not overlay.visible
    old_gen = c.generation_id
    c.analyze()  # Remains locked until worker really finishes.
    assert c.generation_id == old_gen
    pump(qt_app, lambda: not c.busy)
    assert not overlay.results and not overlay.visible
    assert c.budget_snapshot.reserved_usd == 0


def test_timeout_cancels_response_and_retains_uncertain_cost(setup_controller, qt_app):
    c, overlay, _, factory = setup_controller
    factory.client.delay = .1
    c.analyze()
    pump(qt_app, lambda: bool(factory.client.payloads))
    op = c._operation
    op.deadline = time.monotonic() - 1  # API received original deadline.
    c._tick()
    assert c.state is AppState.TIMEOUT
    assert c.budget_snapshot.uncertain_usd > 0
    pump(qt_app, lambda: not c.busy)
    assert not overlay.results
    assert c.budget_snapshot.spent_usd == 0
    assert c.budget_snapshot.uncertain_usd > 0


def test_shutdown_during_request_is_nonblocking(setup_controller, qt_app):
    c, overlay, _, factory = setup_controller
    factory.client.delay = 5
    c.analyze()
    pump(qt_app, lambda: bool(factory.client.payloads))
    started = time.monotonic()
    c.shutdown()
    assert time.monotonic() - started < .1
    pump(qt_app, lambda: not c.busy)
    assert factory.client.closed
    assert not overlay.results
    assert c.budget_snapshot.uncertain_usd > 0


def test_invalid_answer_cost_is_still_counted(setup_controller, qt_app):
    c, overlay, _, factory = setup_controller
    factory.client.answer = {"invalid": "response"}
    c.analyze()
    pump(qt_app, lambda: not c.busy)
    assert c.state is AppState.ERROR
    assert c.budget_snapshot.spent_usd == pytest.approx(.011)
    assert not overlay.results


def test_capture_failure_releases_budget(setup_controller, qt_app):
    c, overlay, capture, _ = setup_controller
    capture.failure = True
    c.analyze()
    pump(qt_app, lambda: not c.busy)
    assert c.state is AppState.ERROR
    assert c.budget_snapshot.reserved_usd == c.budget_snapshot.uncertain_usd == 0
    assert "private" not in overlay.errors[-1]


def test_cancelled_response_usage_not_lost_even_if_provider_ignores_cancel(setup_controller, qt_app):
    c, overlay, _, factory = setup_controller
    c._batch.append(frame())
    # Intercept just the worker dispatch to deterministically deliver a stale response.
    c._run_worker = lambda *args: None
    c.analyze()
    gen = c.generation_id
    c.cancel()
    result = AnalysisResult(QuizAnswer.model_validate(answer_payload()), "gpt-6.1-sol", .1, UsageSummary(10, 10, .001), None)
    c._analysis_succeeded(gen, result)
    c._finish_operation()
    assert not overlay.results
    assert c.budget_snapshot.spent_usd == .001


def test_late_completed_usage_replaces_timeout_reservation(setup_controller):
    c, overlay, _, _ = setup_controller
    c._batch.append(frame())
    c._run_worker = lambda *args: None
    c.analyze()
    gen = c.generation_id
    c._operation.deadline = time.monotonic() - 1
    c._tick()
    assert c.budget_snapshot.uncertain_usd > 0
    result = AnalysisResult(QuizAnswer.model_validate(answer_payload()), "gpt-6.1-sol", .1, UsageSummary(10, 10, .001), None)
    c._analysis_succeeded(gen, result)
    c._finish_operation()
    assert not overlay.results
    assert c.budget_snapshot.spent_usd == .001
    assert c.budget_snapshot.uncertain_usd == 0


def test_snapshot_config_unchanged_mid_request(setup_controller, qt_app):
    c, _, _, factory = setup_controller
    c.analyze()
    c.set_api_provider(c._provider, ApiConfig(model="gpt-6-luna", reasoning_effort="low", deadline_seconds=30))
    pump(qt_app, lambda: not c.busy)
    assert factory.client.payloads[0]["model"] == "gpt-6.1-sol"
