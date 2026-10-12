import base64
import io
import time
from threading import Event, Timer
from types import SimpleNamespace

import pytest
from PIL import Image
from quiz_assistant.ai.provider import OpenAIProvider, ProviderError, ProviderErrorKind, frame_to_png_data_url
from quiz_assistant.models import ApiConfig
from helpers import FakeFactory, frame, answer_payload, part


def provider_for(factory):
    provider = OpenAIProvider(factory)
    provider.configure("sk-test-not-real", ApiConfig())
    return provider


def test_png_only_in_memory_exact_size(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    encoded = frame_to_png_data_url(frame())
    image = Image.open(io.BytesIO(base64.b64decode(encoded.split(",")[1])))
    assert image.size == (2, 2)
    assert image.getpixel((0, 0)) == (30, 20, 10)
    assert list(tmp_path.iterdir()) == []


def test_single_request_contains_six_ordered_images():
    factory = FakeFactory()
    result = provider_for(factory).analyze(tuple(frame(i) for i in range(6)))
    assert len(factory.client.payloads) == 1
    payload = factory.client.payloads[0]
    assert payload["model"] == "gpt-6.1-sol"
    assert payload["reasoning"] == {"effort": "medium"}
    assert payload["max_output_tokens"] == 6000
    assert payload["store"] is False and payload["stream"] is False and payload["tools"] == []
    assert payload["text"]["format"]["strict"] is True
    images = [c for c in payload["input"][0]["content"] if c["type"] == "input_image"]
    assert len(images) == 6
    assert images[0]["image_url"] == frame_to_png_data_url(frame(0))
    assert result.answer.parts[0].answer_text == "4"
    assert result.usage.estimated_cost_usd == pytest.approx(.011)
    assert factory.kwargs["max_retries"] == 0
    assert factory.kwargs["base_url"] == "https://api.openai.com/v1"
    assert factory.client.closed


def test_snapshot_retains_model_and_key():
    factory = FakeFactory()
    provider = provider_for(factory)
    saved = provider.snapshot()
    provider.configure("new-key", ApiConfig(model="gpt-6-luna", reasoning_effort="low"))
    provider.close()
    saved.analyze(frame())
    assert factory.kwargs["api_key"] == "sk-test-not-real"
    assert factory.client.payloads[0]["model"] == "gpt-6.1-sol"


def test_connection_check_does_not_create_response():
    factory = FakeFactory()
    assert provider_for(factory).check_connection() == "gpt-6.1-sol"
    assert factory.client.payloads == []


@pytest.mark.parametrize("mode,kind", [("incomplete", ProviderErrorKind.INCOMPLETE), ("invalid", ProviderErrorKind.INVALID_RESPONSE), ("refusal", ProviderErrorKind.REFUSAL)])
def test_rejected_answers_preserve_usage(mode, kind):
    factory = FakeFactory()
    if mode == "incomplete":
        factory.client.status = "incomplete"
    elif mode == "invalid":
        factory.client.answer = {"bad": "data"}
    else:
        factory.client.output = [SimpleNamespace(content=[SimpleNamespace(type="refusal")])]
    with pytest.raises(ProviderError) as caught:
        provider_for(factory).analyze(frame())
    assert caught.value.kind == kind
    assert caught.value.usage.input_tokens == 2500
    assert not caught.value.cost_uncertain
    assert len(factory.client.payloads) == 1


def test_usage_missing_is_unknown_not_zero():
    result = provider_for(FakeFactory(usage=False)).analyze(frame())
    assert result.usage is None


def test_partial_invalid_part_preserves_valid_code():
    factory = FakeFactory(payload=answer_payload(part("code", "const X = 'A';\n  X !== 'a';"), part(part_id="bad", answer_text=None)))
    result = provider_for(factory).analyze(frame())
    assert result.answer.status.value == "partial"
    assert result.answer.parts[0].answer_text == "const X = 'A';\n  X !== 'a';"
    assert result.answer.parts[1].answer_text is None


def test_deadline_cancels_http_without_retry():
    factory = FakeFactory(delay=5)
    started = time.monotonic()
    with pytest.raises(ProviderError) as caught:
        provider_for(factory).analyze(frame(), deadline=started + .08)
    assert caught.value.kind == ProviderErrorKind.TIMEOUT
    assert caught.value.cost_uncertain
    assert time.monotonic() - started < 1
    assert factory.client.cancelled and factory.client.closed
    assert len(factory.client.payloads) == 1


def test_cancel_request_closes_transport():
    factory = FakeFactory(delay=5)
    cancel = Event()
    timer = Timer(.08, cancel.set)
    timer.start()
    try:
        with pytest.raises(ProviderError) as caught:
            provider_for(factory).analyze(frame(), cancel)
        assert caught.value.kind == ProviderErrorKind.CANCELLED
        assert factory.client.closed and factory.client.cancelled
    finally:
        timer.join()


@pytest.mark.parametrize("mode", ["cancel", "deadline"])
def test_preparation_can_be_aborted_before_request(mode):
    factory = FakeFactory()
    cancel = Event()
    if mode == "cancel":
        cancel.set()
    with pytest.raises(ProviderError) as caught:
        provider_for(factory).analyze(frame(), cancel, deadline=time.monotonic() - 1 if mode == "deadline" else None)
    assert not caught.value.cost_uncertain
    assert factory.client.payloads == []


def test_encoding_time_counts_towards_deadline(monkeypatch):
    from quiz_assistant.ai import provider as module
    original = module.frame_to_png_data_url
    def slow(frame):
        time.sleep(.04)
        return original(frame)
    monkeypatch.setattr(module, "frame_to_png_data_url", slow)
    factory = FakeFactory()
    with pytest.raises(ProviderError) as caught:
        provider_for(factory).analyze(frame(), deadline=time.monotonic() + .01)
    assert caught.value.kind == ProviderErrorKind.TIMEOUT
    assert factory.client.payloads == []


def test_root_unknown_fields_including_sources_are_rejected():
    payload = answer_payload()
    payload["source_ids"] = ["invented"]
    with pytest.raises(ProviderError):
        provider_for(FakeFactory(payload=payload)).analyze(frame())
