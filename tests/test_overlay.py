from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from quiz_assistant.ui import overlay as overlay_module


def test_loading_panel_can_be_shown(monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(overlay_module, "apply_nonactivating_clickthrough", lambda _hwnd: None)
    monkeypatch.setattr(overlay_module, "show_without_activation", lambda _hwnd: None)

    panel = overlay_module.OverlayWindow()
    panel.show_loading(7)
    app.processEvents()

    assert panel.isVisible()
    assert "Analizuję" in panel._answer.text()
    panel.close()
