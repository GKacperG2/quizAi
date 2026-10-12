from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QPlainTextEdit, QTabWidget, QGridLayout,
)
from quiz_assistant.ui.result_text import result_text, capture_times


class MainWindow(QMainWindow):
    action = Signal(str)
    remove_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Asystent quizów")
        self.resize(860, 680)
        self._frames = ()
        self._busy = False
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.status = self._label("Uruchamianie…")
        self.status.setStyleSheet("font-size: 18px; font-weight: 600")
        layout.addWidget(self.status)
        self.summary = self._label("")
        layout.addWidget(self.summary)
        self.budget = self._label("")
        layout.addWidget(self.budget)
        self.elapsed = self._label("")
        layout.addWidget(self.elapsed)
        self._buttons = {}
        bar = QHBoxLayout()
        for key, text in [("analyze", "Analizuj · Ctrl+M"), ("add", "Dodaj ujęcie"), ("cancel", "Anuluj i wyczyść"), ("pause", "Gotowy / Pauza")]:
            button = self._button(key, text)
            bar.addWidget(button)
        layout.addLayout(bar)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        captures = QWidget()
        capture_layout = QVBoxLayout(captures)
        capture_layout.addWidget(self._label("Jedna paczka = jedno pytanie = jedno żądanie API. Maksymalnie 6 ujęć, wyłącznie w RAM."))
        self.list = QListWidget()
        self.list.setMaximumHeight(160)
        self.list.currentRowChanged.connect(self._preview)
        capture_layout.addWidget(self.list)
        tools = QHBoxLayout()
        for label, callback in [
            ("Wyżej", lambda: self.move_requested.emit(self.list.currentRow(), -1)),
            ("Niżej", lambda: self.move_requested.emit(self.list.currentRow(), 1)),
            ("Usuń ujęcie", lambda: self.remove_requested.emit(self.list.currentRow())),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            tools.addWidget(button)
        capture_layout.addLayout(tools)
        self.preview = self._label("Brak ujęć. Ustaw obszar, wróć do pytania i naciśnij Ctrl+Shift+M.\nCtrl+M bez paczki pobierze jeden zrzut.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(200, 120)
        capture_layout.addWidget(self.preview, 1)
        tabs.addTab(captures, "Ujęcia")
        self.result = QPlainTextEdit()
        self.result.setReadOnly(True)
        self.result.setPlaceholderText("Tu pojawi się pełny wynik z uzasadnieniami. Model może się mylić.")
        font = QFont("Consolas", 11)
        self.result.setFont(font)
        tabs.addTab(self.result, "Pełna odpowiedź")
        settings = QWidget()
        grid = QGridLayout(settings)
        for i, (key, text) in enumerate([
            ("api", "Ustawienia API"), ("region", "Ustaw obszar"),
            ("shortcuts", "Skróty"), ("appearance", "Wygląd panelu"),
            ("position", "Pozycja panelu"), ("connection", "Test dostępu do modelu"),
            ("simulator", "Otwórz symulator"), ("diagnostics", "Otwórz dziennik diagnostyczny"),
            ("toggle", "Pokaż / ukryj panel"),
        ]):
            grid.addWidget(self._button(key, text), i // 2, i % 2)
        grid.addWidget(self._label(
            "Analiza wysyła wybrane obrazy do OpenAI i może naliczać opłaty. "
            "Brak automatycznych ponowień. Budżet to lokalny szacunek sesji, nie twardy limit konta.\n"
            "Zawiera krótki, wbudowany kontekst kursu. Bez importu plików, wykonywania kodu "
            "i automatycznego zaznaczania odpowiedzi.\n"
            "Używaj za zgodą prowadzącego. Zamknięcie okna pozostawia program w zasobniku."
        ), 5, 0, 1, 2)
        grid.setRowStretch(6, 1)
        tabs.addTab(settings, "Ustawienia i diagnostyka")
        footer = QHBoxLayout()
        self.notice = self._label("Najpierw ustaw obszar i klucz API w zakładce Ustawienia.")
        footer.addWidget(self.notice, 1)
        footer.addWidget(self._button("quit", "Zakończ program"))
        layout.addLayout(footer)

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        return label

    def _button(self, key, text):
        button = QPushButton(text)
        button.clicked.connect(lambda: self.action.emit(key))
        self._buttons[key] = button
        return button

    def set_busy(self, busy):
        self._busy = busy
        for key, button in self._buttons.items():
            button.setEnabled(not busy or key in ("cancel", "quit", "toggle", "diagnostics"))

    def set_frames(self, frames):
        old_index = self.list.currentRow()
        self._frames = frames
        self.list.clear()
        for i, frame in enumerate(frames, 1):
            self.list.addItem(f"{i}. {frame.width}×{frame.height} px · {capture_times((frame,))}")
        self.list.setCurrentRow(min(max(0, old_index), len(frames) - 1))
        self._preview(self.list.currentRow())

    def _preview(self, index):
        self.preview.clear()
        if not 0 <= index < len(self._frames):
            self.preview.setText("Brak ujęć. Ctrl+Shift+M dodaje ujęcie, Ctrl+M analizuje.")
            return
        frame = self._frames[index]
        image = QImage(frame.bgra_bytes, frame.width, frame.height, frame.width * 4, QImage.Format.Format_RGB32).copy()
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            max(200, self.preview.width()), max(120, self.preview.height()),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "preview"):
            self._preview(self.list.currentRow())

    def show_result(self, generation, result, frames):
        self.result.setPlainText(result_text(generation, result, frames))

    def show_main(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
