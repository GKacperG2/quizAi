from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from quiz_assistant.ai.schemas import AnswerStatus, QuestionType
from quiz_assistant.models import OverlayAppearance
from quiz_assistant.platform.windows.native_window import apply_nonactivating_clickthrough, show_without_activation
from quiz_assistant.ui.result_text import part_text, capture_times


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(22, 18, 22, 18)
        self._layout.setSpacing(10)
        self._eyebrow = self._label("ASYSTENT QUIZÓW")
        self._eyebrow.setObjectName("eyebrow")
        self._answer = self._label("")
        self._answer.setObjectName("heading")
        self._body = QVBoxLayout()
        self._layout.addLayout(self._body)
        self._meta = self._label("")
        self._meta.setObjectName("meta")
        self._content = False
        self._loading = False
        self._rendered_result = None
        self.apply_appearance(OverlayAppearance())

    def _label(self, text, layout=None, code=False):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        if code:
            label.setObjectName("code")
        (layout or self._layout).addWidget(label)
        return label

    def _reset_body(self):
        while self._body.count():
            item = self._body.takeAt(0)
            item.widget().hide()
            item.widget().deleteLater()

    def clear(self):
        self.hide()
        self._content = False
        self._loading = False
        self._rendered_result = None
        self._reset_body()
        self._answer.clear()
        self._meta.clear()

    def apply_appearance(self, appearance):
        self.appearance = appearance
        self.setFixedWidth(appearance.width)
        base = round(10 + appearance.brightness * .55) if appearance.theme == "dark" else round(205 + appearance.brightness * .5)
        self._background = QColor(base, base, base, round(255 * appearance.opacity / 100))
        text = round(170 + appearance.contrast * .85) if appearance.theme == "dark" else round(95 - appearance.contrast * .95)
        accent = "#9ecbff" if appearance.theme == "dark" else "#14529b"
        self.setStyleSheet(
            f"QLabel {{ color: rgb({text},{text},{text}); background: transparent; font-size: {appearance.font_size}px; }}"
            f"QLabel#eyebrow, QLabel#meta {{ color: {accent}; font-size: 12px; }}"
            f"QLabel#heading {{ font-weight: 700; }}"
            'QLabel#code { font-family: "Consolas", "Courier New", monospace; }'
        )
        if self._rendered_result is not None:
            self._render_result(*self._rendered_result)
        self.adjustSize()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._background)
        painter.setPen(QPen(QColor("#609ffa"), 1.5))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

    def show_loading(self, generation_id, elapsed=0, limit=20):
        self._rendered_result = None
        self._reset_body()
        self._loading = True
        self._content = True
        self._eyebrow.setText("ANALIZA API")
        self._answer.setText("Analizuję zapisane ujęcia…")
        self._generation = generation_id
        self.update_progress(elapsed, limit)
        self._show_nonactivating()

    def update_progress(self, elapsed, limit):
        if self._loading:
            self._meta.setText(f"Generacja #{self._generation} · {elapsed:.1f} / {limit:g} s")

    def show_analysis_result(self, generation_id, result, frames=(), elapsed=None):
        self._loading = False
        self._content = True
        self._rendered_result = (generation_id, result, frames, elapsed)
        self._render_result(*self._rendered_result)
        self._show_nonactivating()

    def _render_result(self, generation_id, result, frames, elapsed):
        self._reset_body()
        answer = result.answer
        self._eyebrow.setText("SUGESTIA MODELU — ZWERYFIKUJ")
        question = answer.question_text or "Nie rozpoznano pytania"
        self._answer.setText(question[:180] + ("… [skrót]" if len(question) > 180 else ""))
        self._meta.setText(
            f"#{generation_id} · zrzuty {capture_times(frames)} · {result.model}\n"
            f"{elapsed if elapsed is not None else result.elapsed_seconds:.1f} s · wynik dla zapisanych ujęć"
        )
        screen = self.screen() or QGuiApplication.primaryScreen()
        maximum = min(680, screen.availableGeometry().height() - 40) if screen else 680
        truncated = len(question) > 180
        if answer.reason:
            self._label(answer.reason[:250], self._body)
            truncated |= len(answer.reason) > 250
        for i, part in enumerate(answer.parts, 1):
            text = f"{i}. {part.label}\n{part_text(part)}"
            if part.explanation:
                text += "\n" + part.explanation
            if part.warnings:
                text += "\nUwaga: " + "; ".join(part.warnings)
            short = text[:500] + ("… [skrót]" if len(text) > 500 else "")
            truncated |= len(text) > 500
            label = self._label(short, self._body, part.question_type in (QuestionType.CODE, QuestionType.CODE_OUTPUT))
            self._layout.activate()
            self.adjustSize()
            if self.sizeHint().height() > maximum - 55:
                self._body.removeWidget(label)
                label.hide()
                label.deleteLater()
                truncated = True
                break
        if answer.warnings:
            truncated = True
        if truncated:
            self._label("Wynik skrócony. Pełna treść i uwagi w oknie głównym.", self._body)
        self.adjustSize()

    def show_error(self, message):
        self._rendered_result = None
        self._reset_body()
        self._loading = False
        self._content = True
        self._eyebrow.setText("BRAK WYNIKU")
        self._answer.setText(message)
        self._meta.setText("Poprzednia sugestia nie jest aktywna.")
        self._show_nonactivating()

    def show_preview(self):
        self._rendered_result = None
        self._reset_body()
        self._loading = False
        self._content = True
        self._eyebrow.setText("PODGLĄD WYGLĄDU — NIE ODPOWIEDŹ")
        self._answer.setText("1. Przykładowe pole")
        self._label("Czytelny tekst na tle panelu.\n2. Przykład kodu:", self._body)
        self._label("Maybe.of(2).map(x => x + 1)", self._body, True)
        self._meta.setText("Zmiany wyglądu są widoczne na żywo.")
        self._show_nonactivating()

    def toggle(self):
        if self.isVisible():
            self.hide()
        elif self._content:
            self._show_nonactivating()

    def showEvent(self, event):
        super().showEvent(event)
        apply_nonactivating_clickthrough(int(self.winId()))
        show_without_activation(int(self.winId()))

    def _show_nonactivating(self):
        self.adjustSize()
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            r = screen.availableGeometry()
            self.move(max(r.left(), min(self.x(), r.right() - self.width() + 1)),
                      max(r.top(), min(self.y(), r.bottom() - self.height() + 1)))
        self.show()
        apply_nonactivating_clickthrough(int(self.winId()))
        show_without_activation(int(self.winId()))
