"""Render only synthetic UI data for local visual QA. Never captures a desktop or quiz."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QColor, QFontDatabase, QFont
from quiz_assistant.ui.main_window import MainWindow
from quiz_assistant.ui.dialogs import AppearanceDialog
from quiz_assistant.ui import overlay as overlay_module
from quiz_assistant.models import OverlayAppearance
from quiz_assistant.ai.provider import AnalysisResult
from quiz_assistant.ai.schemas import QuizAnswer


def main():
    app = QApplication([])
    for name in ("segoeui.ttf", "consola.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
    app.setFont(QFont("Segoe UI", 10))
    overlay_module.apply_nonactivating_clickthrough = lambda _: None
    overlay_module.show_without_activation = lambda _: None
    answer = QuizAnswer.model_validate({
        "status": "ok", "question_text": "Przykład testowy: jaki jest wynik map?",
        "reason": None, "warnings": [], "parts": [{
            "part_id": "p1", "label": "Wynik wykonania kodu", "question_type": "code_output",
            "status": "ok", "options": [], "targets": [], "selected_positions": [],
            "answer_text": "[2, 4, 6]", "matches": [], "ordered_positions": [],
            "explanation": "Każdy element został pomnożony przez 2.", "reason": None, "warnings": [],
        }],
    })
    result = AnalysisResult(answer, "DEMO — BEZ API", .4, None, None)
    window = MainWindow()
    window.status.setText("Gotowy — przykład testowy interfejsu")
    window.summary.setText("Sol / medium · 20 s · obszar nie ustawiony")
    window.budget.setText("Budżet sesji: 0 / 0,50 USD")
    window.show_result(1, result, ())
    window.show()
    panel = overlay_module.OverlayWindow()
    panel.show_analysis_result(1, result)
    dialog = AppearanceDialog(OverlayAppearance())
    dialog.show()
    app.processEvents()
    canvas = QPixmap(1400, 920)
    canvas.fill(QColor("#dde2e8"))
    painter = QPainter(canvas)
    painter.drawPixmap(10, 10, window.grab())
    painter.drawPixmap(890, 10, panel.grab())
    painter.drawPixmap(890, 310, dialog.grab())
    panel.apply_appearance(OverlayAppearance(theme="light", width=420))
    app.processEvents()
    painter.drawPixmap(890, 680, panel.grab())
    painter.end()
    destination = Path(__file__).resolve().parents[1] / ".artifacts" / "ui-review.png"
    destination.parent.mkdir(exist_ok=True)
    canvas.save(str(destination))
    print(destination)


if __name__ == "__main__":
    main()
