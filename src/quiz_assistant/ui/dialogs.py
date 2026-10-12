from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QKeySequenceEdit,
    QSpinBox,
    QPushButton,
)

from quiz_assistant.models import ApiConfig, HotkeyAction, OverlayAppearance
from quiz_assistant.platform.windows.hotkeys import parse_hotkey_sequence


class ShortcutDialog(QDialog):
    _LABELS = {
        HotkeyAction.ANALYZE: "Analizuj zrzut lub paczkę:",
        HotkeyAction.ADD_FRAME: "Dodaj ujęcie do paczki:",
        HotkeyAction.TOGGLE_OVERLAY: "Pokaż / schowaj panel:",
        HotkeyAction.CANCEL: "Anuluj:",
    }

    def __init__(self, shortcuts: dict[HotkeyAction, str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Skróty globalne")
        self._editors: dict[HotkeyAction, QKeySequenceEdit] = {}

        layout = QVBoxLayout(self)
        note = QLabel("Każdy skrót musi zawierać co najmniej jeden modyfikator.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        for action, label in self._LABELS.items():
            editor = QKeySequenceEdit(QKeySequence(shortcuts[action]))
            editor.setMaximumSequenceLength(1)
            self._editors[action] = editor
            form.addRow(label, editor)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def shortcuts(self) -> dict[HotkeyAction, str]:
        return {
            action: editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for action, editor in self._editors.items()
        }

    def accept(self) -> None:
        shortcuts = self.shortcuts()
        try:
            parsed = [parse_hotkey_sequence(value) for value in shortcuts.values()]
            if len(set(parsed)) != len(parsed):
                raise ValueError("Każda akcja musi mieć inny skrót.")
        except ValueError as exc:
            QMessageBox.warning(self, "Nieprawidłowe skróty", str(exc))
            return
        super().accept()


class ApiSettingsDialog(QDialog):
    def __init__(
        self,
        config: ApiConfig,
        *,
        key_present: bool,
        key_source: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ustawienia OpenAI API")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        note = QLabel(
            "Klucz jest przechowywany w Windows Credential Manager, nie w pliku projektu. "
            f"Aktualne źródło: {key_source if key_present else 'brak klucza'}."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()
        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText(
            "Klucz już zapisany — pozostaw puste" if key_present else "sk-…"
        )
        self._api_key.setEnabled(key_source != "zmienna OPENAI_API_KEY")
        form.addRow("Klucz API:", self._api_key)

        self._model = QComboBox()
        self._model.addItems(["gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra"])
        if self._model.findText(config.model) < 0:
            self._model.addItem(config.model)
        self._model.setCurrentText(config.model)
        self._model.currentTextChanged.connect(self._model_changed)
        form.addRow("Model:", self._model)

        self._effort = QComboBox()
        self._effort.addItems(["none", "low", "medium", "high", "xhigh", "max"])
        self._effort.setCurrentText(config.reasoning_effort)
        form.addRow("Reasoning effort:", self._effort)

        self._image_detail = QComboBox()
        self._image_detail.addItems(["auto", "high", "low"])
        self._image_detail.setCurrentText(config.image_detail)
        form.addRow("Szczegółowość obrazu:", self._image_detail)

        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(128, 16000)
        self._max_tokens.setValue(config.max_output_tokens)
        form.addRow("Maks. tokenów wyjścia:", self._max_tokens)

        self._timeout = QDoubleSpinBox()
        self._timeout.setRange(3.0, 60.0)
        self._timeout.setSuffix(" s")
        self._timeout.setDecimals(1)
        self._timeout.setValue(config.deadline_seconds)
        form.addRow("Limit oczekiwania:", self._timeout)

        self._budget = QDoubleSpinBox()
        self._budget.setRange(0.01, 100.0)
        self._budget.setDecimals(2)
        self._budget.setPrefix("$")
        self._budget.setValue(config.session_budget_usd)
        form.addRow("Limit kosztu sesji:", self._budget)
        self._preset = QComboBox()
        self._preset.addItems(["Własne / zapisane", "Sol medium — domyślny", "Sol low — porównaj szybkość", "Luna low — ekonomiczny"])
        self._preset.currentIndexChanged.connect(self._apply_preset)
        form.addRow("Zastosuj profil:", self._preset)
        layout.addLayout(form)

        self._remove_key = QCheckBox("Usuń zapisany klucz z Windows Credential Manager")
        self._remove_key.setEnabled(key_present and key_source != "zmienna OPENAI_API_KEY")
        if key_source == "zmienna OPENAI_API_KEY":
            note.setText(note.text() + " Zmienna środowiskowa ma pierwszeństwo; usuń ją poza aplikacją, aby używać magazynu Windows.")
        layout.addWidget(self._remove_key)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._model_changed(self._model.currentText())

    def config(self) -> ApiConfig:
        return ApiConfig(
            model=self._model.currentText(),
            reasoning_effort=self._effort.currentText(),
            image_detail=self._image_detail.currentText(),
            max_output_tokens=self._max_tokens.value(),
            deadline_seconds=self._timeout.value(),
            session_budget_usd=self._budget.value(),
        )

    def entered_api_key(self) -> str:
        return self._api_key.text().strip()

    def remove_key_requested(self) -> bool:
        return self._remove_key.isChecked()

    def _model_changed(self, model: str) -> None:
        previous = self._effort.currentText()
        self._effort.clear()
        self._effort.addItems((["none"] if model == "gpt-6-luna" else []) + ["low", "medium", "high", "xhigh", "max"])
        self._effort.setCurrentText(previous if self._effort.findText(previous) >= 0 else "low")

    def _apply_preset(self, index):
        if not index:
            return
        self._model.setCurrentText("gpt-6-luna" if index == 3 else "gpt-6.1-sol")
        self._effort.setCurrentText("medium" if index == 1 else "low")
        self._timeout.setValue(20)
        self._max_tokens.setValue(6000)

    def accept(self):
        try:
            self.config()
        except ValueError as exc:
            QMessageBox.warning(self, "Ustawienia API", str(exc))
            return
        super().accept()


class AppearanceDialog(QDialog):
    changed = Signal(object)

    def __init__(self, appearance, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wygląd podpowiedzi")
        layout = QVBoxLayout(self)
        note = QLabel("Podgląd na żywo. Krycie dotyczy tylko tła — tekst pozostaje nieprzezroczysty.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self._theme = QComboBox()
        self._theme.addItem("Ciemny", "dark")
        self._theme.addItem("Jasny", "light")
        self._theme.setCurrentIndex(0 if appearance.theme == "dark" else 1)
        form.addRow("Motyw:", self._theme)
        self._editors = {}
        for name, title, low, high, suffix in (
            ("opacity", "Krycie tła:", 50, 100, "%"),
            ("brightness", "Jasność tła:", 0, 100, "%"),
            ("contrast", "Kontrast tekstu:", 0, 100, "%"),
            ("font_size", "Rozmiar tekstu:", 12, 24, " px"),
            ("width", "Szerokość panelu:", 320, 720, " px"),
        ):
            editor = QSpinBox()
            editor.setRange(low, high)
            editor.setSuffix(suffix)
            editor.setValue(getattr(appearance, name))
            self._editors[name] = editor
            editor.valueChanged.connect(self._changed)
            form.addRow(title, editor)
        self._theme.currentIndexChanged.connect(self._changed)
        layout.addLayout(form)
        reset = QPushButton("Przywróć domyślne")
        reset.clicked.connect(self._reset)
        layout.addWidget(reset)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def appearance(self):
        return OverlayAppearance(theme=self._theme.currentData(),
                                 **{k: v.value() for k, v in self._editors.items()})

    def _changed(self):
        self.changed.emit(self.appearance())

    def _reset(self):
        defaults = OverlayAppearance()
        self._theme.setCurrentIndex(0)
        for name, editor in self._editors.items():
            editor.setValue(getattr(defaults, name))


class PanelPositionDialog(QDialog):
    def __init__(self, initial_position: QPoint, parent=None) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("panelPositionDialog")
        self.setFixedWidth(420)
        self._drag_offset: QPoint | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        title = QLabel("USTAW POZYCJĘ PANELU")
        title.setObjectName("title")
        note = QLabel("Przeciągnij to okno, następnie wybierz Zapisz.")
        note.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setStyleSheet(
            """
            QDialog#panelPositionDialog {
                background: #121826; border: 2px solid #60a5fa; border-radius: 16px;
            }
            QLabel { color: #f8fafc; }
            QLabel#title { color: #93c5fd; font-weight: 800; }
            """
        )
        self.adjustSize()
        self.move(initial_position)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
