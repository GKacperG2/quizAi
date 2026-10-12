from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from quiz_assistant.geometry import logical_rect_to_physical
from quiz_assistant.models import CaptureRegion, MonitorDescriptor


class RegionSelector(QWidget):
    selected = Signal(object)
    cancelled = Signal()

    def __init__(self, monitor: MonitorDescriptor) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self._monitor = monitor
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(
            monitor.logical_left,
            monitor.logical_top,
            monitor.logical_width,
            monitor.logical_height,
        )

    def show_selector(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._end = event.position().toPoint()
        rect = QRect(self._start, self._end).normalized().intersected(self.rect())
        if rect.width() < 20 or rect.height() < 20:
            self._start = None
            self._end = None
            self.update()
            return
        x_px, y_px, width_px, height_px = logical_rect_to_physical(
            rect.x(),
            rect.y(),
            rect.width(),
            rect.height(),
            self._monitor.device_pixel_ratio,
        )
        region = CaptureRegion(
            monitor_id=self._monitor.monitor_id,
            x_px=x_px,
            y_px=y_px,
            width_px=min(width_px, self._monitor.physical_width - x_px),
            height_px=min(height_px, self._monitor.physical_height - y_px),
            configured_dpi=self._monitor.dpi,
            monitor_width_px=self._monitor.physical_width,
            monitor_height_px=self._monitor.physical_height,
        )
        self.selected.emit(region)
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(6, 10, 20, 155))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._start is not None and self._end is not None:
            rect = QRect(self._start, self._end).normalized().intersected(self.rect())
            painter.fillRect(rect, QColor(37, 99, 235, 48))
            painter.setPen(QPen(QColor("#60a5fa"), 2))
            painter.drawRect(rect)
            text = f"{rect.width()} × {rect.height()} jednostek logicznych"
            painter.setPen(QColor("#ffffff"))
            painter.drawText(rect.adjusted(10, 10, -10, -10), Qt.AlignmentFlag.AlignTop, text)

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            self.rect().adjusted(24, 24, -24, -24),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            "Przeciągnij obszar pytania · Esc anuluje",
        )
