from __future__ import annotations

from threading import Event
from PySide6.QtCore import QObject, Signal, Slot
from quiz_assistant.ai.provider import OpenAIProvider, ProviderError, ProviderErrorKind
from quiz_assistant.models import CaptureFrame


class AnalysisWorker(QObject):
    analyzed = Signal(int, object)
    failed = Signal(int, object)
    finished = Signal()

    def __init__(self, generation_id: int, provider: OpenAIProvider,
                 frames: tuple[CaptureFrame, ...], cancel: Event, deadline: float) -> None:
        super().__init__()
        self._generation_id = generation_id
        self._provider = provider
        self._frames = frames
        self._cancel = cancel
        self._deadline = deadline

    @Slot()
    def run(self) -> None:
        try:
            result = self._provider.analyze(self._frames, self._cancel, self._deadline)
        except ProviderError as exc:
            self.failed.emit(self._generation_id, exc)
        except Exception:
            self.failed.emit(self._generation_id, ProviderError(
                ProviderErrorKind.API, "Nieoczekiwany błąd analizy.", cost_uncertain=True,
            ))
        else:
            self.analyzed.emit(self._generation_id, result)
        finally:
            self._frames = ()
            self.finished.emit()


class ConnectionTestWorker(QObject):
    succeeded = Signal(str)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, provider: OpenAIProvider, cancel: Event | None = None) -> None:
        super().__init__()
        self._provider = provider
        self.cancel = cancel or Event()

    @Slot()
    def run(self) -> None:
        try:
            model = self._provider.check_connection(self.cancel)
        except ProviderError as exc:
            self.failed.emit(exc)
        except Exception:
            self.failed.emit(ProviderError(ProviderErrorKind.API, "Błąd testu połączenia."))
        else:
            self.succeeded.emit(model)
        finally:
            self.finished.emit()
