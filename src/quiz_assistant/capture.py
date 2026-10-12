from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from typing import Any

import mss
from PySide6.QtCore import QObject, Signal, Slot

from quiz_assistant.geometry import absolute_capture_rect
from quiz_assistant.models import CaptureFrame, CaptureRegion, MonitorDescriptor


class CaptureService:
    def __init__(self, mss_factory: Callable[[], Any] = mss.mss) -> None:
        self._mss_factory = mss_factory

    def capture(
        self,
        region: CaptureRegion,
        monitor: MonitorDescriptor,
    ) -> CaptureFrame:
        capture_rect = absolute_capture_rect(region, monitor)
        with self._mss_factory() as session:
            screenshot = session.grab(capture_rect)
            bgra = bytes(screenshot.bgra)

        return CaptureFrame(
            width=int(screenshot.width),
            height=int(screenshot.height),
            bgra_bytes=bgra,
            captured_at=time.monotonic(),
            sha256=hashlib.sha256(bgra).hexdigest(),
        )


class CaptureWorker(QObject):
    captured = Signal(int, object)
    failed = Signal(int, str)
    finished = Signal()

    def __init__(
        self,
        generation_id: int,
        service: CaptureService,
        region: CaptureRegion,
        monitor: MonitorDescriptor,
    ) -> None:
        super().__init__()
        self._generation_id = generation_id
        self._service = service
        self._region = region
        self._monitor = monitor

    @Slot()
    def run(self) -> None:
        try:
            frame = self._service.capture(self._region, self._monitor)
        except Exception as exc:  # boundary: OS capture failures become UI state
            self.failed.emit(self._generation_id, str(exc))
        else:
            self.captured.emit(self._generation_id, frame)
        finally:
            self.finished.emit()
