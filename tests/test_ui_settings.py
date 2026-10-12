from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QLabel, QDialog
from quiz_assistant.config import SettingsStore
from quiz_assistant.models import ApiConfig, OverlayAppearance
from quiz_assistant.ai.provider import AnalysisResult
from quiz_assistant.ai.schemas import QuizAnswer
from quiz_assistant.ui.dialogs import ApiSettingsDialog, AppearanceDialog
from quiz_assistant.ui.main_window import MainWindow
from quiz_assistant.ui.overlay import OverlayWindow
from helpers import part, answer_payload, frame


def test_appearance_persist_defaults_and_corruption(tmp_path):
    qsettings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    store = SettingsStore(qsettings)
    assert store.load_appearance() == OverlayAppearance()
    appearance = OverlayAppearance(theme="light", opacity=50, brightness=10, contrast=80, font_size=24, width=720)
    store.save_appearance(appearance)
    assert store.load_appearance() == appearance
    qsettings.setValue("appearance/width", -1)
    assert store.load_appearance() == OverlayAppearance()


def test_api_dialog_preserves_config_on_open_and_profiles_keep_budget():
    config = ApiConfig(model="gpt-6-luna", reasoning_effort="high", session_budget_usd=.27)
    dialog = ApiSettingsDialog(config, key_present=False, key_source="")
    assert dialog.config() == config
    dialog._preset.setCurrentIndex(1)
    assert dialog.config() == ApiConfig(session_budget_usd=.27)
    dialog._preset.setCurrentIndex(2)
    assert dialog.config().reasoning_effort == "low"
    assert dialog.config().deadline_seconds == 20
    dialog.close()


def test_appearance_live_preview_and_reset():
    dialog = AppearanceDialog(OverlayAppearance(width=720))
    changes = []
    dialog.changed.connect(changes.append)
    dialog._editors["opacity"].setValue(60)
    assert changes[-1].opacity == 60
    dialog._reset()
    assert dialog.appearance() == OverlayAppearance()
    dialog.close()


def test_main_close_hides_and_second_activation_reopens(qt_app):
    main = MainWindow()
    main.show()
    main.close()
    assert not main.isVisible()
    main.show_main()
    assert main.isVisible()
    main.hide()


def test_overlay_plain_text_code_and_truncation(monkeypatch, qt_app):
    from quiz_assistant.ui import overlay as module
    monkeypatch.setattr(module, "apply_nonactivating_clickthrough", lambda _: None)
    monkeypatch.setattr(module, "show_without_activation", lambda _: None)
    panel = OverlayWindow()
    answer = QuizAnswer.model_validate(answer_payload(
        part("code", "const X = '<b>A</b>';\n  X !== 'a';"),
        part("open", "tekst " * 1000, part_id="p2")))
    result = AnalysisResult(answer, "offline", .1, None, None)
    panel.show_analysis_result(3, result, (frame(),))
    qt_app.processEvents()
    labels = panel.findChildren(QLabel)
    assert all(label.textFormat() == Qt.TextFormat.PlainText for label in labels)
    assert any("<b>A</b>" in label.text() for label in labels)
    assert any("skrócony" in label.text() for label in labels)
    flags = panel.windowFlags()
    assert flags & Qt.WindowType.WindowDoesNotAcceptFocus
    assert flags & Qt.WindowType.WindowTransparentForInput
    assert panel.windowOpacity() == 1.0
    assert panel._background.alpha() == round(.95 * 255)
    main = MainWindow()
    main.show_result(3, result, (frame(),))
    assert "tekst " * 1000 in main.result.toPlainText()
    panel.clear()
    panel.toggle()
    assert not panel.isVisible()
    main.hide()


def test_batch_preview_and_removal_signal():
    main = MainWindow()
    main.set_frames((frame(), frame(50)))
    assert main.list.count() == 2
    assert not main.preview.pixmap().isNull()
    main.set_frames(())
    assert main.list.count() == 0
    main.hide()
