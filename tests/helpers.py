import asyncio
import json
import time
from types import SimpleNamespace
from quiz_assistant.models import CaptureFrame


def frame(value=10):
    return CaptureFrame(2, 2, bytes([value, 20, 30, 255]) * 4, time.monotonic(), str(value) * 32)


def part(kind="open", text="4", **changes):
    value = dict(
        part_id="p1", label="Pole 1", question_type=kind, status="ok",
        options=[], targets=[], selected_positions=[], answer_text=text,
        matches=[], ordered_positions=[], explanation="Uzasadnienie.", reason=None, warnings=[],
    )
    value.update(changes)
    return value


def answer_payload(*parts):
    return dict(status="ok", question_text="Pytanie", parts=list(parts) or [part()], reason=None, warnings=[])


def option(position, text):
    return dict(position=position, label=chr(64 + position), text=text)


class FakeClient:
    def __init__(self, payload=None, delay=0, status="completed", usage=True):
        self.answer = payload if payload is not None else answer_payload()
        self.delay, self.status, self.usage = delay, status, usage
        self.payloads = []
        self.closed = False
        self.cancelled = False
        self.responses = SimpleNamespace(create=self.create)
        self.models = SimpleNamespace(retrieve=self.retrieve)
        self.failure = None
        self.output = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def create(self, **kwargs):
        self.payloads.append(kwargs)
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            status=self.status, output_text=json.dumps(self.answer), output=self.output,
            usage=SimpleNamespace(input_tokens=2500, output_tokens=600) if self.usage else None,
            _request_id="req_test",
        )

    async def retrieve(self, model):
        await asyncio.sleep(self.delay)
        return SimpleNamespace(id=model)


class FakeFactory:
    def __init__(self, **kwargs):
        self.client = FakeClient(**kwargs)
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self.client
