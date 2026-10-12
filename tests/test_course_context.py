from quiz_assistant.ai.course_context import (
    COURSE_CONTEXT,
    COURSE_CONTEXT_TOKEN_RESERVE,
    COURSE_CONTEXT_VERSION,
)
from quiz_assistant.ai.prompts import SYSTEM_INSTRUCTIONS
from quiz_assistant.ai.provider import OpenAIProvider
from quiz_assistant.models import ApiConfig
from helpers import FakeFactory, frame


def test_curated_context_is_versioned_and_embedded_in_system_instructions():
    assert COURSE_CONTEXT_VERSION in SYSTEM_INSTRUCTIONS
    assert COURSE_CONTEXT in SYSTEM_INSTRUCTIONS
    assert COURSE_CONTEXT_TOKEN_RESERVE >= 2_000


def test_context_contains_corrected_core_distinctions():
    assert "składanie jest łączne" in COURSE_CONTEXT
    assert "Currying" in COURSE_CONTEXT and "nie identyczne" in COURSE_CONTEXT
    assert "Monada nie jest po prostu pudełkiem" in COURSE_CONTEXT
    assert "Maybe nie jest pełnym" in COURSE_CONTEXT
    assert "widoczne na obrazie mają pierwszeństwo" in COURSE_CONTEXT


def test_provider_sends_curated_context_as_instructions():
    factory = FakeFactory()
    provider = OpenAIProvider(factory)
    provider.configure("sk-test-not-real", ApiConfig())

    provider.analyze(frame())

    instructions = factory.client.payloads[0]["instructions"]
    assert COURSE_CONTEXT_VERSION in instructions
    assert "POMOCNICZY KONTEKST KURSU" in instructions
