from __future__ import annotations

import asyncio
import base64
import io
import json
import time
from dataclasses import dataclass
from enum import Enum
from threading import Event
from typing import Any, Callable

import openai
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from quiz_assistant.ai.prompts import SYSTEM_INSTRUCTIONS, USER_INSTRUCTION
from quiz_assistant.ai.schemas import QUIZ_ANSWER_JSON_SCHEMA, QuizAnswer, validate_answer_payload
from quiz_assistant.budget import calculate_measured_cost
from quiz_assistant.models import ApiConfig, CaptureFrame


class ProviderErrorKind(str, Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CONNECTION = "connection"
    INCOMPLETE = "incomplete"
    REFUSAL = "refusal"
    INVALID_RESPONSE = "invalid_response"
    API = "api"


@dataclass(frozen=True, slots=True)
class UsageSummary:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class ProviderError(RuntimeError):
    def __init__(self, kind: ProviderErrorKind, user_message: str, *,
                 request_id: str | None = None, cost_uncertain: bool = False,
                 usage: UsageSummary | None = None) -> None:
        super().__init__(user_message)
        self.kind = kind
        self.user_message = user_message
        self.request_id = request_id
        self.cost_uncertain = cost_uncertain
        self.usage = usage


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    answer: QuizAnswer
    model: str
    elapsed_seconds: float
    usage: UsageSummary | None
    request_id: str | None


class OpenAIProvider:
    """Configuration holder. Each worker owns and closes its async HTTP transport."""
    def __init__(self, client_factory: Callable[..., Any] = AsyncOpenAI) -> None:
        self._client_factory = client_factory
        self._credentials: tuple[str, ApiConfig] | None = None

    @property
    def ready(self) -> bool:
        return self._credentials is not None

    def configure(self, api_key: str, config: ApiConfig) -> None:
        if not api_key.strip():
            raise ValueError("Brak klucza API.")
        self._credentials = (api_key.strip(), config)

    def close(self) -> None:
        self._credentials = None

    def snapshot(self) -> "OpenAIProvider":
        provider = OpenAIProvider(self._client_factory)
        provider._credentials = self._credentials
        return provider

    def check_connection(self, cancel: Event | None = None) -> str:
        credentials = self._credentials
        if credentials is None:
            raise ProviderError(ProviderErrorKind.AUTH, "Najpierw zapisz klucz API.")
        key, config = credentials

        async def run():
            async with self._client_factory(
                api_key=key, base_url="https://api.openai.com/v1",
                max_retries=0, timeout=config.deadline_seconds,
            ) as client:
                model = await _interruptible(
                    client.models.retrieve(config.model), cancel or Event(),
                    time.monotonic() + config.deadline_seconds, cost_uncertain=False,
                )
                return str(model.id)
        try:
            return asyncio.run(run())
        except Exception as exc:
            raise _map_exception(exc) from exc

    def analyze(self, frames: tuple[CaptureFrame, ...] | CaptureFrame,
                cancel: Event | None = None, deadline: float | None = None) -> AnalysisResult:
        credentials = self._credentials
        if credentials is None:
            raise ProviderError(ProviderErrorKind.AUTH, "Brak skonfigurowanego klucza API.")
        key, config = credentials
        frames = (frames,) if isinstance(frames, CaptureFrame) else tuple(frames)
        if not 1 <= len(frames) <= 6:
            raise ProviderError(ProviderErrorKind.API, "Paczka musi zawierać 1–6 ujęć.")
        started = time.monotonic()
        deadline = deadline if deadline is not None else started + config.deadline_seconds
        cancel = cancel or Event()
        content = [{"type": "input_text", "text": USER_INSTRUCTION}]
        for index, frame in enumerate(frames):
            _check_deadline(cancel, deadline, sent=False)
            content.append({"type": "input_text", "text": f"Ujęcie {index + 1} z {len(frames)}:"})
            content.append({
                "type": "input_image", "image_url": frame_to_png_data_url(frame),
                "detail": config.image_detail,
            })
        _check_deadline(cancel, deadline, sent=False)

        async def run():
            async with self._client_factory(
                api_key=key, base_url="https://api.openai.com/v1",
                max_retries=0, timeout=max(0.1, deadline - time.monotonic()),
            ) as client:
                return await _interruptible(client.responses.create(
                    model=config.model, instructions=SYSTEM_INSTRUCTIONS,
                    input=[{"role": "user", "content": content}],
                    reasoning={"effort": config.reasoning_effort},
                    text={"format": {
                        "type": "json_schema", "name": "quiz_answer_v2", "strict": True,
                        "schema": QUIZ_ANSWER_JSON_SCHEMA,
                    }},
                    max_output_tokens=config.max_output_tokens, store=False, stream=False,
                    tools=[],
                ), cancel, deadline, cost_uncertain=True)
        try:
            response = asyncio.run(run())
        except Exception as exc:
            raise _map_exception(exc) from exc
        request_id = getattr(response, "_request_id", None)
        usage = _read_usage(response, config.model)
        error_details = dict(request_id=request_id, usage=usage, cost_uncertain=usage is None)
        if getattr(response, "status", None) != "completed":
            raise ProviderError(
                ProviderErrorKind.INCOMPLETE,
                "Model nie ukończył odpowiedzi. Spróbuj profilu low lub zwiększ limit wyjścia.",
                **error_details,
            )
        if any(getattr(c, "type", None) == "refusal"
               for item in getattr(response, "output", []) or []
               for c in getattr(item, "content", []) or []):
            raise ProviderError(ProviderErrorKind.REFUSAL, "Model odmówił odpowiedzi.", **error_details)
        try:
            answer = validate_answer_payload(json.loads(getattr(response, "output_text", "")))
        except (ValidationError, ValueError, TypeError):
            raise ProviderError(
                ProviderErrorKind.INVALID_RESPONSE,
                "Niespójna struktura odpowiedzi API. Nie pokazuję niezwalidowanego wyniku.",
                **error_details,
            ) from None
        return AnalysisResult(answer, config.model, time.monotonic() - started, usage, request_id)


def _check_deadline(cancel: Event, deadline: float, *, sent: bool) -> None:
    if cancel.is_set():
        raise ProviderError(ProviderErrorKind.CANCELLED, "Anulowano analizę.", cost_uncertain=sent)
    if time.monotonic() >= deadline:
        raise ProviderError(ProviderErrorKind.TIMEOUT, "Przekroczono limit czasu analizy.", cost_uncertain=sent)


async def _interruptible(awaitable, cancel: Event, deadline: float, *, cost_uncertain: bool):
    task = asyncio.create_task(awaitable)
    try:
        while not task.done():
            _check_deadline(cancel, deadline, sent=cost_uncertain)
            await asyncio.wait({task}, timeout=min(0.05, max(0.001, deadline - time.monotonic())))
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def _read_usage(response, model: str) -> UsageSummary | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    incoming, outgoing = getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)
    if not isinstance(incoming, int) or not isinstance(outgoing, int) or min(incoming, outgoing) < 0:
        return None
    return UsageSummary(incoming, outgoing, calculate_measured_cost(model, incoming, outgoing))


def frame_to_png_data_url(frame: CaptureFrame, max_long_edge: int = 2400) -> str:
    image = Image.frombytes("RGB", (frame.width, frame.height), frame.bgra_bytes, "raw", "BGRX")
    if max(image.size) > max_long_edge:
        scale = max_long_edge / max(image.size)
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                             Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=3)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _map_exception(exc: Exception) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    request_id = getattr(exc, "request_id", None)
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ProviderError(ProviderErrorKind.AUTH, "Nieprawidłowy klucz lub brak dostępu do modelu.",
                             request_id=request_id)
    if isinstance(exc, openai.RateLimitError):
        return ProviderError(ProviderErrorKind.RATE_LIMIT, "Limit API lub brak środków na koncie.",
                             request_id=request_id)
    if isinstance(exc, openai.APITimeoutError):
        return ProviderError(ProviderErrorKind.TIMEOUT, "Przekroczono limit czasu analizy.",
                             request_id=request_id, cost_uncertain=True)
    if isinstance(exc, openai.APIConnectionError):
        return ProviderError(ProviderErrorKind.CONNECTION, "Nie udało się połączyć z OpenAI.",
                             cost_uncertain=True)
    if isinstance(exc, openai.APIStatusError):
        return ProviderError(ProviderErrorKind.API, f"API zwróciło błąd HTTP {exc.status_code}.",
                             request_id=request_id, cost_uncertain=exc.status_code >= 500)
    return ProviderError(ProviderErrorKind.API, "Nieoczekiwany błąd analizy.", cost_uncertain=True)
