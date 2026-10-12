from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Event

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt

from quiz_assistant.ai.provider import AnalysisResult, OpenAIProvider, ProviderError, ProviderErrorKind
from quiz_assistant.ai.schemas import AnswerStatus
from quiz_assistant.ai.worker import AnalysisWorker
from quiz_assistant.budget import BudgetLedger, estimate_request_reservation
from quiz_assistant.capture import CaptureService, CaptureWorker
from quiz_assistant.geometry import region_is_valid
from quiz_assistant.models import ApiConfig, AppState, CaptureFrame, CaptureRegion, HotkeyAction
from quiz_assistant.monitors import find_monitor
from quiz_assistant.platform.windows.native_window import flush_compositor

log = logging.getLogger("quiz_assistant")


@dataclass
class Operation:
    generation: int
    config: ApiConfig
    provider: OpenAIProvider | None
    started: float
    deadline: float
    collect: bool = False
    frames: tuple[CaptureFrame, ...] = ()
    cancel: Event = field(default_factory=Event)
    invalid: bool = False
    sent: bool = False
    reserved: bool = False


class SessionController(QObject):
    state_changed = Signal(object, str)
    notification = Signal(str, str)
    budget_changed = Signal(object)
    batch_changed = Signal(object)
    result_ready = Signal(int, object, object)
    result_cleared = Signal()
    progress = Signal(float, float)
    capture_preparing = Signal()
    idle = Signal()

    def __init__(self, overlay, capture_service: CaptureService | None = None) -> None:
        super().__init__()
        self._overlay = overlay
        self._capture_service = capture_service or CaptureService()
        self._provider = None
        self._api_config = ApiConfig()
        self._budget = BudgetLedger(self._api_config.session_budget_usd)
        self._state = AppState.UNCONFIGURED
        self._state_reason = "Ustaw obszar i API."
        self._region = None
        self._monitors = []
        self._hotkeys_ready = False
        self._paused = False
        self._closing = False
        self._external_busy = False
        self._generation_id = 0
        self._operation: Operation | None = None
        self._thread = None
        self._worker = None
        self._pending_stage = None
        self._batch: list[CaptureFrame] = []
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)
        self._ticker.timeout.connect(self._tick)

    @property
    def state(self):
        return self._state

    @property
    def state_reason(self):
        return self._state_reason

    @property
    def generation_id(self):
        return self._generation_id

    @property
    def busy(self):
        return self._operation is not None or self._external_busy

    @property
    def budget_snapshot(self):
        return self._budget.snapshot()

    @property
    def frames(self):
        return tuple(self._batch)

    def set_external_busy(self, busy: bool):
        self._external_busy = busy

    def configure_environment(self, monitors, region):
        self._monitors, self._region = monitors, region
        if not self.busy:
            self._refresh_idle_state()

    def set_region(self, region: CaptureRegion):
        self._region = region
        if not self.busy:
            self._refresh_idle_state()

    def set_hotkeys_ready(self, ready, reason=""):
        self._hotkeys_ready = ready
        if not ready and reason:
            self._set_state(AppState.UNCONFIGURED, reason)
        elif not self.busy:
            self._refresh_idle_state()

    def set_api_provider(self, provider, config: ApiConfig):
        self._provider, self._api_config = provider, config
        self._budget.set_limit(config.session_budget_usd)
        self.budget_changed.emit(self.budget_snapshot)
        if not self.busy:
            self._refresh_idle_state()

    @Slot(bool)
    def set_ready_enabled(self, enabled):
        self._paused = not enabled
        if self._paused:
            self.cancel()
        self._refresh_idle_state()

    @Slot(object)
    def handle_hotkey(self, action):
        if action == HotkeyAction.ANALYZE:
            self.analyze()
        elif action == HotkeyAction.ADD_FRAME:
            self.add_frame()
        elif action == HotkeyAction.TOGGLE_OVERLAY:
            self._overlay.toggle()
        elif action == HotkeyAction.CANCEL:
            self.cancel()

    def _can_begin(self):
        if self.busy or self._closing:
            self.notification.emit("Operacja trwa", "Poczekaj na zakończenie lub anuluj bieżącą operację.")
            return False
        if self._paused or not self._hotkeys_ready:
            self.notification.emit("Wstrzymano", "Włącz Gotowy i sprawdź skróty.")
            return False
        return True

    def add_frame(self):
        if len(self._batch) >= 6:
            self.notification.emit("Paczka pełna", "Maksymalnie 6 ujęć. Usuń zbędne ujęcie w oknie głównym.")
            return
        self._begin(collect=True)

    def analyze(self):
        self._begin(collect=False)

    def _begin(self, *, collect):
        if not self._can_begin():
            return
        monitor = find_monitor(self._monitors, self._region.monitor_id) if self._region else None
        needs_capture = collect or not self._batch
        if needs_capture and not region_is_valid(self._region, monitor):
            self._set_state(AppState.UNCONFIGURED, "Ustaw obszar ponownie: monitor, geometria lub DPI są nieprawidłowe.")
            self.notification.emit("Obszar", self._state_reason)
            return
        if not collect and (self._provider is None or not self._provider.ready):
            self._set_state(AppState.UNCONFIGURED, "Skonfiguruj klucz API.")
            self.notification.emit("API", self._state_reason)
            return
        self._generation_id += 1
        now = time.monotonic()
        op = Operation(
            self._generation_id, self._api_config,
            self._provider.snapshot() if self._provider else None,
            now, now + self._api_config.deadline_seconds, collect=collect,
            frames=() if collect else tuple(self._batch),
        )
        self._overlay.clear()
        self.result_cleared.emit()
        if not collect:
            key = str(op.generation)
            if not self._budget.reserve(key, estimate_request_reservation(op.config, len(op.frames) or 1)):
                self._set_state(AppState.ERROR, "Brak rezerwy budżetu. Zmień limit lub profil w ustawieniach API.")
                self.notification.emit("Budżet", self._state_reason)
                return
            op.reserved = True
            self.budget_changed.emit(self.budget_snapshot)
        self._operation = op
        self._ticker.start()
        if needs_capture:
            self._set_state(AppState.CAPTURING, "Zapisuję ujęcie w pamięci…")
            self.capture_preparing.emit()
            region = self._region
            QTimer.singleShot(0, lambda: self._start_capture(op, region, monitor))
        else:
            self._batch.clear()
            self.batch_changed.emit(self.frames)
            self._start_analysis(op)

    def _start_capture(self, op, region, monitor):
        if not self._is_current(op):
            self._finish_operation()
            return
        if not flush_compositor():
            self._capture_failed(op.generation, "")
            self._finish_operation()
            return
        worker = CaptureWorker(op.generation, self._capture_service, region, monitor)
        self._run_worker(worker, worker.captured, self._capture_succeeded, worker.failed, self._capture_failed)

    def _start_analysis(self, op):
        if not self._is_current(op):
            self._finish_operation()
            return
        if self._expired(op):
            self._finish_operation()
            return
        self._overlay.show_loading(op.generation, 0, op.config.deadline_seconds)
        self._set_state(AppState.REQUESTING, f"Analiza {len(op.frames)} ujęć — {op.config.model}.")
        op.sent = True
        worker = AnalysisWorker(op.generation, op.provider, op.frames, op.cancel, op.deadline)
        self._run_worker(worker, worker.analyzed, self._analysis_succeeded, worker.failed, self._analysis_failed)

    def _run_worker(self, worker, success, succeeded, failure, failed):
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        success.connect(succeeded)
        failure.connect(failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._worker_thread_finished)
        self._thread, self._worker = thread, worker
        thread.start()

    @Slot(int, object)
    def _capture_succeeded(self, generation, frame):
        op = self._operation
        if not op or op.generation != generation or not self._is_current(op) or self._expired(op):
            return
        log.info("capture_complete generation=%s width=%s height=%s hash=%s duration_ms=%s",
                 generation, frame.width, frame.height, frame.sha256,
                 round((time.monotonic() - op.started) * 1000))
        if op.collect:
            if sum(len(item.bgra_bytes) for item in self._batch) + len(frame.bgra_bytes) > 256 * 1024 * 1024:
                self._set_state(AppState.ERROR, "Paczka przekroczyłaby limit 256 MiB. Zmniejsz obszar.")
                return
            self._batch.append(frame)
            self.batch_changed.emit(self.frames)
            self._set_state(AppState.READY, f"Paczka: {len(self._batch)}/6 ujęć. Ctrl+M analizuje paczkę.")
            self.notification.emit("Ujęcie dodane", self._state_reason)
        else:
            op.frames = (frame,)
            self._pending_stage = lambda: self._start_analysis(op)

    @Slot(int, str)
    def _capture_failed(self, generation, _message):
        op = self._operation
        if op and op.generation == generation and self._is_current(op):
            self._overlay.show_error("Nie udało się przechwycić obrazu. Sprawdź obszar i monitor.")
            self._set_state(AppState.ERROR, "Błąd przechwytywania.")
            log.warning("capture_failed generation=%s", generation)

    @Slot(int, object)
    def _analysis_succeeded(self, generation: int, result: AnalysisResult):
        op = self._operation
        if not op or op.generation != generation:
            return
        self._settle(op, result.usage, uncertain=result.usage is None)
        if not self._is_current(op) or self._expired(op):
            return
        self._set_state(AppState.VALIDATING, "Sprawdzam odpowiedzi pól…")
        elapsed = time.monotonic() - op.started
        self._overlay.show_analysis_result(generation, result, op.frames, elapsed)
        self.result_ready.emit(generation, result, op.frames)
        state = AppState.SHOWING_RESULT if result.answer.status in (AnswerStatus.OK, AnswerStatus.PARTIAL) else AppState.UNCERTAIN
        self._set_state(state, f"Wynik dla zrzutu #{generation} · {elapsed:.1f} s.")
        log.info("analysis_complete generation=%s status=%s", generation, result.answer.status.value)

    @Slot(int, object)
    def _analysis_failed(self, generation: int, error: ProviderError):
        op = self._operation
        if not op or op.generation != generation:
            return
        self._settle(op, error.usage, uncertain=error.cost_uncertain)
        log.warning("analysis_failed generation=%s kind=%s", generation, error.kind.value)
        if not self._is_current(op) or self._expired(op):
            return
        self._overlay.show_error(error.user_message)
        self._set_state(AppState.TIMEOUT if error.kind == ProviderErrorKind.TIMEOUT else AppState.ERROR, error.user_message)

    def _settle(self, op, usage, *, uncertain):
        if not op.reserved:
            return
        key = str(op.generation)
        if usage is not None:
            self._budget.reconcile(key, usage.estimated_cost_usd)
        elif uncertain:
            self._budget.mark_uncertain(key)
        else:
            self._budget.release(key)
        op.reserved = False
        self.budget_changed.emit(self.budget_snapshot)

    def _is_current(self, op):
        return self._operation is op and not op.invalid and not self._closing

    def _expired(self, op):
        if time.monotonic() < op.deadline:
            return False
        if self._is_current(op):
            op.invalid = True
            op.cancel.set()
            self._pending_stage = None
            self._overlay.show_error(f"Przekroczono limit {op.config.deadline_seconds:g} s. Wynik nie zostanie pokazany.")
            self._set_state(AppState.TIMEOUT, "Przekroczono limit całej analizy.")
            if op.reserved and op.sent:
                self._budget.mark_uncertain(str(op.generation))
                self.budget_changed.emit(self.budget_snapshot)
        return True

    @Slot()
    def _tick(self):
        op = self._operation
        if op and self._is_current(op):
            elapsed = time.monotonic() - op.started
            self.progress.emit(elapsed, op.config.deadline_seconds)
            self._overlay.update_progress(elapsed, op.config.deadline_seconds)
            self._expired(op)

    @Slot()
    def _worker_thread_finished(self):
        thread, self._thread = self._thread, None
        self._worker = None
        if thread:
            thread.deleteLater()
        pending, self._pending_stage = self._pending_stage, None
        if pending and self._operation and self._is_current(self._operation):
            pending()
        else:
            self._finish_operation()

    def _finish_operation(self):
        op = self._operation
        if op and op.reserved:
            self._settle(op, None, uncertain=op.sent)
        self._operation = None
        self._pending_stage = None
        self._ticker.stop()
        self.idle.emit()

    def remove_frame(self, index):
        if not self.busy and 0 <= index < len(self._batch):
            self._batch.pop(index)
            self.batch_changed.emit(self.frames)

    def move_frame(self, index, offset):
        target = index + offset
        if not self.busy and 0 <= index < len(self._batch) and 0 <= target < len(self._batch):
            self._batch[index], self._batch[target] = self._batch[target], self._batch[index]
            self.batch_changed.emit(self.frames)

    def clear_batch(self):
        if not self.busy:
            self._batch.clear()
            self.batch_changed.emit(self.frames)

    def cancel(self):
        self._generation_id += 1
        op = self._operation
        if op:
            op.invalid = True
            op.cancel.set()
        self._pending_stage = None
        self._batch.clear()
        self.batch_changed.emit(self.frames)
        self._overlay.clear()
        self.result_cleared.emit()
        self._refresh_idle_state()

    def shutdown(self):
        self._closing = True
        self.cancel()
        # Runtime waits via idle/thread.finished signals; never block the GUI.

    def _refresh_idle_state(self):
        if self._paused:
            self._set_state(AppState.PAUSED, "Aplikacja jest wstrzymana.")
        elif not self._hotkeys_ready:
            self._set_state(AppState.UNCONFIGURED, "Globalne skróty nie są aktywne.")
        elif not region_is_valid(self._region, find_monitor(self._monitors, self._region.monitor_id) if self._region else None):
            self._set_state(AppState.UNCONFIGURED, "Ustaw obszar przechwytywania.")
        elif self._provider is None or not self._provider.ready:
            self._set_state(AppState.UNCONFIGURED, "Skonfiguruj klucz OpenAI API.")
        else:
            self._set_state(AppState.READY, "Gotowy — Ctrl+M analizuje zrzut, Ctrl+Shift+M dodaje ujęcie.")

    def _set_state(self, state, reason):
        self._state, self._state_reason = state, reason
        self.state_changed.emit(state, reason)
