from __future__ import annotations

import sys
import logging
from threading import Event
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QThread, QUrl, Qt, Slot
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QInputDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from quiz_assistant.ai.key_store import ApiKeyStore
from quiz_assistant.ai.provider import OpenAIProvider
from quiz_assistant.ai.worker import ConnectionTestWorker
from quiz_assistant.config import SettingsStore
from quiz_assistant.controller import SessionController
from quiz_assistant.models import AppState, CaptureRegion, HotkeyAction, PanelPosition
from quiz_assistant.monitors import enumerate_monitors, find_monitor
from quiz_assistant.platform.windows.dpi import enable_per_monitor_v2_awareness
from quiz_assistant.platform.windows.hotkeys import HotkeyService
from quiz_assistant.single_instance import SingleInstanceGuard, InstanceResult
from quiz_assistant.diagnostics import configure_logging
from quiz_assistant.ui.dialogs import ApiSettingsDialog, PanelPositionDialog, ShortcutDialog, AppearanceDialog
from quiz_assistant.ui.main_window import MainWindow
from quiz_assistant.ui.overlay import OverlayWindow
from quiz_assistant.ui.region_selector import RegionSelector


class QuizAssistantRuntime(QObject):
    def __init__(self, application: QApplication, guard: SingleInstanceGuard, log_path: Path) -> None:
        super().__init__(application)
        self._closing = False
        self._log_path = log_path
        self._connection_cancel = Event()
        self._application = application
        self._guard = guard
        self._settings = SettingsStore()
        try:
            self._monitors = enumerate_monitors()
        except Exception:
            self._monitors = []
            logging.getLogger("quiz_assistant").warning("monitor_enumeration_failed")
        self._region = self._settings.load_region()
        self._shortcuts = self._settings.load_shortcuts()
        self._api_config = self._settings.load_api_config()
        self._key_store = ApiKeyStore()
        self._provider = OpenAIProvider()
        self._selector: RegionSelector | None = None
        self._connection_thread: QThread | None = None
        self._connection_worker: ConnectionTestWorker | None = None
        self._screen_signal_ids: set[int] = set()

        self._overlay = OverlayWindow()
        self._overlay.apply_appearance(self._settings.load_appearance())
        self._main = MainWindow()
        self._apply_saved_panel_position()
        self._controller = SessionController(self._overlay)
        self._controller.configure_environment(self._monitors, self._region)
        self._controller.state_changed.connect(self._on_state_changed)
        self._controller.batch_changed.connect(self._main.set_frames)
        self._controller.result_ready.connect(self._main.show_result)
        self._controller.result_cleared.connect(self._main.result.clear)
        self._controller.result_cleared.connect(self._main.elapsed.clear)
        self._controller.progress.connect(self._on_progress)
        self._controller.capture_preparing.connect(self._main.hide)
        self._controller.idle.connect(self._on_idle)
        self._main.remove_requested.connect(self._controller.remove_frame)
        self._main.move_requested.connect(self._controller.move_frame)
        self._main.action.connect(self._main_action)
        try:
            api_key = self._key_store.get_key()
        except Exception:
            api_key = None
        if api_key:
            self._provider.configure(api_key, self._api_config)
            self._controller.set_api_provider(self._provider, self._api_config)
        else:
            self._controller.set_api_provider(None, self._api_config)

        self._hotkeys = HotkeyService(application)
        self._hotkeys.triggered.connect(self._handle_hotkey)
        hotkeys_ok, hotkey_error = self._hotkeys.register(self._shortcuts)
        self._controller.set_hotkeys_ready(hotkeys_ok, hotkey_error)

        self._tray = QSystemTrayIcon(_create_tray_icon(), application)
        self._menu = QMenu()
        self._status_action = self._menu.addAction("Uruchamianie…")
        self._status_action.setEnabled(False)
        self._budget_action = self._menu.addAction("Budżet sesji: ładowanie…")
        self._budget_action.setEnabled(False)
        self._menu.addSeparator()
        self._menu.addAction("Otwórz okno główne", self._main.show_main)
        self._ready_action = self._menu.addAction("Gotowy")
        self._ready_action.setCheckable(True)
        self._ready_action.setChecked(True)
        self._ready_action.toggled.connect(self._controller.set_ready_enabled)
        self._menu.addAction("Ustaw obszar…", self.select_region)
        self._menu.addAction("Ustaw pozycję panelu…", self.select_panel_position)
        self._menu.addAction("Wygląd panelu…", self.configure_appearance)
        self._menu.addAction("Ustaw skróty…", self.configure_shortcuts)
        self._menu.addAction("Ustawienia OpenAI API…", self.configure_api)
        self._menu.addAction("Testuj połączenie API", self.test_api_connection)
        self._menu.addSeparator()
        self._menu.addAction("Pokaż / ukryj panel", self._overlay.toggle)
        self._menu.addAction("Otwórz symulator", self.open_simulator)
        self._menu.addSeparator()
        self._menu.addAction("Zakończ", self.shutdown)
        self._tray.setContextMenu(self._menu)
        self._tray.setToolTip("Asystent quizów — lokalny klient OpenAI")
        self._controller.notification.connect(self.show_notification)
        self._controller.budget_changed.connect(self._on_budget_changed)
        self._guard.activation_requested.connect(self._show_existing_instance)
        self._tray.activated.connect(self._tray_activated)

        self._application.screenAdded.connect(lambda _screen: self.refresh_monitors())
        self._application.screenRemoved.connect(lambda _screen: self.refresh_monitors())
        self._connect_screen_signals()

        self._tray.show()
        self._on_state_changed(self._controller.state, self._state_reason())
        self._on_budget_changed(self._controller.budget_snapshot)
        self._refresh_summary()
        self._main.show_main()
        if not hotkeys_ok:
            self.show_notification("Konflikt skrótu", hotkey_error)
        elif self._region is None:
            self.show_notification(
                "Wymagana konfiguracja",
                "Otwórz menu ikony w zasobniku i wybierz „Ustaw obszar…”.",
            )
        elif not api_key:
            self.show_notification(
                "Wymagana konfiguracja API",
                "Otwórz menu ikony w zasobniku i wybierz „Ustawienia OpenAI API…”.",
            )

    def _state_reason(self) -> str:
        return self._controller.state_reason

    @Slot()
    def select_region(self) -> None:
        if not self._can_configure():
            return
        self.refresh_monitors()
        if not self._monitors:
            QMessageBox.warning(
                None,
                "Brak monitora",
                "Nie udało się powiązać monitorów Qt z fizycznymi ekranami MSS.",
            )
            return

        monitor = self._choose_monitor()
        if monitor is None:
            return
        self._overlay.hide()
        self._main.hide()
        self._selector = RegionSelector(monitor)
        self._selector.selected.connect(self._region_selected)
        self._selector.cancelled.connect(lambda: setattr(self, "_selector", None))
        self._selector.destroyed.connect(lambda: setattr(self, "_selector", None))
        self._selector.show_selector()

    @Slot(object)
    def _region_selected(self, region: CaptureRegion) -> None:
        self._region = region
        self._settings.save_region(region)
        self._controller.set_region(region)
        self._refresh_summary()
        self._selector = None
        self.show_notification(
            "Obszar zapisany",
            f"Kadr: {region.width_px}×{region.height_px} px. Ctrl+M uruchamia analizę.",
        )

    @Slot()
    def select_panel_position(self) -> None:
        if not self._can_configure():
            return
        initial = self._overlay.pos()
        if initial.isNull():
            initial = self._default_panel_position()
        dialog = PanelPositionDialog(initial)
        dialog.setFixedWidth(self._overlay.width())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        center = dialog.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        monitor = find_monitor(self._monitors, screen.name())
        if monitor is None:
            self.refresh_monitors()
            monitor = find_monitor(self._monitors, screen.name())
        if monitor is None:
            QMessageBox.warning(None, "Błąd pozycji", "Nie udało się rozpoznać monitora.")
            return
        local = dialog.pos() - screen.geometry().topLeft()
        position = PanelPosition(monitor.monitor_id, local.x(), local.y())
        self._settings.save_panel_position(position)
        self._apply_panel_position(position)

    @Slot()
    def configure_shortcuts(self) -> None:
        if not self._can_configure():
            return
        dialog = ShortcutDialog(self._shortcuts)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        proposed = dialog.shortcuts()
        old = self._shortcuts
        ok, error = self._hotkeys.register(proposed)
        if not ok:
            restored, restore_error = self._hotkeys.register(old)
            self._controller.set_hotkeys_ready(restored, restore_error or error)
            QMessageBox.warning(
                None,
                "Nie udało się zapisać skrótów",
                f"{error}\n\nPrzywrócono poprzednią konfigurację."
                if restored
                else f"{error}\n\nNie udało się też przywrócić skrótów: {restore_error}",
            )
            return
        self._shortcuts = proposed
        self._settings.save_shortcuts(proposed)
        self._controller.set_hotkeys_ready(True)
        self._refresh_summary()
        self.show_notification("Skróty zapisane", "Nowe skróty globalne są aktywne.")

    @Slot()
    def configure_api(self) -> None:
        if not self._can_configure():
            return
        try:
            existing_key = self._key_store.get_key()
            source = self._key_store.source_label()
        except Exception:
            QMessageBox.warning(
                None,
                "Błąd magazynu poświadczeń",
                "Nie udało się odczytać Windows Credential Manager. Sprawdź dostęp do magazynu systemowego.",
            )
            return

        dialog = ApiSettingsDialog(
            self._api_config,
            key_present=bool(existing_key),
            key_source=source,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            if dialog.remove_key_requested():
                self._key_store.delete_key()
                existing_key = None
            entered_key = dialog.entered_api_key()
            if entered_key:
                self._key_store.save_key(entered_key)
                existing_key = entered_key

            config = dialog.config()
            self._settings.save_api_config(config)
            self._api_config = config
            self._refresh_summary()
            if not existing_key:
                self._provider.close()
                self._controller.set_api_provider(None, config)
                self.show_notification("Brak klucza API", "Zapisz klucz, aby uruchamiać analizę.")
                return
            self._provider.configure(existing_key, config)
            self._controller.set_api_provider(self._provider, config)
        except Exception:
            self._provider.close()
            self._controller.set_api_provider(None, self._api_config)
            QMessageBox.warning(None, "Błąd ustawień API", "Nie udało się zapisać konfiguracji lub klucza w magazynie Windows.")
            return

        self.show_notification(
            "API skonfigurowane",
            f"Model {config.model} jest gotowy. Pierwsze płatne żądanie nastąpi dopiero po Ctrl+M.",
        )

    @Slot()
    def test_api_connection(self) -> None:
        if self._closing:
            return
        if self._controller.busy:
            self.show_notification("Analiza trwa", "Poczekaj na zakończenie bieżącego pytania.")
            return
        if not self._provider.ready:
            self.show_notification(
                "Brak konfiguracji API", "Najpierw zapisz klucz w ustawieniach OpenAI API."
            )
            return
        if self._connection_thread is not None:
            self.show_notification("Test trwa", "Poczekaj na wynik bieżącego testu połączenia.")
            return
        thread = QThread(self._application)
        self._connection_cancel = Event()
        worker = ConnectionTestWorker(self._provider.snapshot(), self._connection_cancel)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._connection_succeeded)
        worker.failed.connect(self._connection_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._connection_test_finished)
        self._connection_thread = thread
        self._connection_worker = worker
        self._controller.set_external_busy(True)
        self._main.set_busy(True)
        self.show_notification("Test API", "Sprawdzam klucz i dostęp do modelu…")
        thread.start()

    @Slot()
    def _connection_test_finished(self) -> None:
        thread = self._connection_thread
        self._connection_thread = None
        self._connection_worker = None
        self._controller.set_external_busy(False)
        self._main.set_busy(self._controller.busy)
        if thread is not None:
            thread.deleteLater()
        self._maybe_finish_shutdown()

    @Slot()
    def open_simulator(self) -> None:
        simulator = Path(__file__).resolve().parents[2] / "simulator" / "index.html"
        if not simulator.exists():
            QMessageBox.warning(None, "Brak symulatora", f"Nie znaleziono pliku:\n{simulator}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(simulator)))

    @Slot()
    def refresh_monitors(self) -> None:
        try:
            self._monitors = enumerate_monitors()
        except Exception:
            self._monitors = []
            self.show_notification("Błąd monitorów", "Nie udało się odczytać konfiguracji ekranów.")
        self._controller.configure_environment(self._monitors, self._region)
        self._connect_screen_signals()
        self._apply_saved_panel_position()

    @Slot(object, str)
    def _on_state_changed(self, state: AppState, reason: str) -> None:
        labels = {
            AppState.UNCONFIGURED: "Nieskonfigurowany",
            AppState.READY: "Gotowy",
            AppState.PAUSED: "Pauza",
            AppState.CAPTURING: "Przechwytywanie",
            AppState.REQUESTING: "Analiza API",
            AppState.VALIDATING: "Walidacja odpowiedzi",
            AppState.SHOWING_RESULT: "Wynik",
            AppState.UNCERTAIN: "Brak pewnej odpowiedzi",
            AppState.TIMEOUT: "Przekroczono czas",
            AppState.ERROR: "Błąd",
        }
        self._main.status.setText(f"{labels[state]} — {reason}")
        self._main.set_busy(self._controller.busy)
        if hasattr(self, "_status_action"):
            self._status_action.setText(f"{labels[state]} — {reason}")
            self._tray.setToolTip(f"Asystent quizów — {labels[state]}")
        if hasattr(self, "_ready_action"):
            self._ready_action.blockSignals(True)
            self._ready_action.setChecked(state is not AppState.PAUSED)
            self._ready_action.setText("Gotowy" if state is not AppState.PAUSED else "Pauza")
            self._ready_action.blockSignals(False)

    @Slot(object)
    def _on_budget_changed(self, snapshot) -> None:
        used = snapshot.spent_usd + snapshot.uncertain_usd
        pending = snapshot.reserved_usd
        text = f"Budżet sesji: ${used:.4f} / ${snapshot.limit_usd:.2f}"
        if pending:
            text += f" · rezerwa ${pending:.4f}"
        if snapshot.uncertain_usd:
            text += f" · niepewne ${snapshot.uncertain_usd:.4f}"
        if hasattr(self, "_budget_action"):
            self._budget_action.setText(text)
        self._main.budget.setText(text)

    @Slot(str, str)
    def show_notification(self, title: str, message: str) -> None:
        if self._closing:
            return
        self._main.notice.setText(f"{title}: {message}")
        if hasattr(self, "_tray"):
            self._tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    @Slot()
    def _show_existing_instance(self) -> None:
        self._main.show_main()

    @Slot()
    def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._main.setEnabled(False)
        self._main.status.setText("Kończę operację i zamykam program…")
        self._hotkeys.close()
        self._connection_cancel.set()
        self._controller.shutdown()
        self._maybe_finish_shutdown()

    def _maybe_finish_shutdown(self):
        if not self._closing or self._controller.busy or self._connection_thread is not None:
            return
        self._provider.close()
        self._guard.close()
        self._tray.hide()
        self._main.hide()
        logging.getLogger("quiz_assistant").info("application_stop")
        self._application.quit()

    @Slot()
    def _on_idle(self):
        self._main.set_busy(self._controller.busy)
        self._maybe_finish_shutdown()

    @Slot(float, float)
    def _on_progress(self, elapsed, limit):
        self._main.elapsed.setText(f"Upłynęło {elapsed:.1f} s / limit {limit:g} s")

    @Slot(str)
    def _connection_succeeded(self, model):
        self.show_notification("Połączenie działa", f"Klucz ma dostęp do {model}. Jakość i czas odpowiedzi nie były testowane.")

    @Slot(object)
    def _connection_failed(self, error):
        self.show_notification("Błąd połączenia API", error.user_message)

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._main.show_main()

    def _can_configure(self):
        if self._controller.busy or self._selector is not None or self._closing:
            self.show_notification("Operacja trwa", "Zakończ lub anuluj operację przed zmianą ustawień.")
            return False
        return True

    def _refresh_summary(self):
        region = f"{self._region.width_px}×{self._region.height_px} px" if self._region else "nie ustawiono"
        keys = " · ".join(f"{action.name}: {key}" for action, key in self._shortcuts.items())
        self._main.summary.setText(
            f"{self._api_config.model} / {self._api_config.reasoning_effort} · {self._api_config.deadline_seconds:g} s · obszar: {region}\n{keys}"
        )

    @Slot(str)
    def _main_action(self, action):
        actions = {
            "analyze": self._controller.analyze, "add": self._controller.add_frame,
            "cancel": self._cancel_all, "pause": lambda: self._controller.set_ready_enabled(self._controller.state is AppState.PAUSED),
            "region": self.select_region, "api": self.configure_api, "appearance": self.configure_appearance,
            "position": self.select_panel_position, "shortcuts": self.configure_shortcuts,
            "connection": self.test_api_connection, "simulator": self.open_simulator,
            "toggle": self._overlay.toggle, "quit": self.shutdown,
            "diagnostics": lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_path))),
        }
        actions[action]()

    def _cancel_all(self):
        self._connection_cancel.set()
        self._controller.cancel()
        if self._selector is not None:
            self._selector.close()
            self._selector = None

    @Slot(object)
    def _handle_hotkey(self, action):
        if action is HotkeyAction.CANCEL:
            self._cancel_all()
        elif QApplication.activeModalWidget() is None and self._selector is None and not self._closing:
            self._controller.handle_hotkey(action)

    def configure_appearance(self):
        if not self._can_configure():
            return
        original = self._overlay.appearance
        was_visible = self._overlay.isVisible()
        showing_preview = not self._overlay._content
        if showing_preview:
            self._overlay.show_preview()
        elif not was_visible:
            self._overlay.toggle()
        dialog = AppearanceDialog(original, self._main)
        dialog.changed.connect(self._overlay.apply_appearance)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings.save_appearance(dialog.appearance())
        else:
            self._overlay.apply_appearance(original)
        if showing_preview:
            self._overlay.clear()
        elif not was_visible:
            self._overlay.hide()

    def _choose_monitor(self):
        if len(self._monitors) == 1:
            return self._monitors[0]
        labels = [monitor.label for monitor in self._monitors]
        selected, accepted = QInputDialog.getItem(
            None,
            "Wybierz monitor",
            "Monitor z pytaniem:",
            labels,
            0,
            False,
        )
        if not accepted:
            return None
        return self._monitors[labels.index(selected)]

    def _connect_screen_signals(self) -> None:
        for screen in QGuiApplication.screens():
            screen_id = id(screen)
            if screen_id in self._screen_signal_ids:
                continue
            self._screen_signal_ids.add(screen_id)
            screen.geometryChanged.connect(lambda _rect: self.refresh_monitors())
            screen.physicalDotsPerInchChanged.connect(lambda _dpi: self.refresh_monitors())

    def _default_panel_position(self) -> QPoint:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QPoint(24, 24)
        available = screen.availableGeometry()
        width = max(self._overlay.width(), 420)
        return QPoint(available.right() - width - 24, available.top() + 24)

    def _apply_saved_panel_position(self) -> None:
        self._apply_panel_position(self._settings.load_panel_position())

    def _apply_panel_position(self, position: PanelPosition | None) -> None:
        target = self._default_panel_position()
        screen = QGuiApplication.primaryScreen()
        if position is not None:
            monitor = find_monitor(self._monitors, position.monitor_id)
            if monitor is not None:
                candidate_screen = next(
                    (item for item in QGuiApplication.screens() if item.name() == monitor.monitor_id),
                    None,
                )
                if candidate_screen is not None:
                    screen = candidate_screen
                    target = candidate_screen.geometry().topLeft() + QPoint(
                        position.x_logical, position.y_logical
                    )
        if screen is not None:
            available = screen.availableGeometry()
            target.setX(
                min(max(target.x(), available.left()), available.right() - self._overlay.width() + 1)
            )
            target.setY(
                min(max(target.y(), available.top()), available.bottom() - self._overlay.height() + 1)
            )
        self._overlay.move(target)


def _create_tray_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(30)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Q")
    painter.end()
    return QIcon(pixmap)


def main() -> int:
    enable_per_monitor_v2_awareness()
    application = QApplication(sys.argv)
    application.setOrganizationName("Kacper")
    application.setApplicationName("QuizAssistantPoC")
    application.setApplicationDisplayName("Asystent quizów")
    application.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(
            None,
            "Brak zasobnika systemowego",
            "Systemowy zasobnik jest niedostępny. Nie można uruchomić aplikacji.",
        )
        return 2

    guard = SingleInstanceGuard("quiz-assistant-poc-kacper-v1")
    result = guard.acquire()
    if result is InstanceResult.ALREADY_RUNNING:
        return 0
    if result is InstanceResult.ERROR:
        QMessageBox.critical(None, "Nie udało się uruchomić", guard.error)
        return 2

    try:
        log_path = configure_logging()
        runtime = QuizAssistantRuntime(application, guard, log_path)
    except Exception as exc:
        logging.getLogger("quiz_assistant").error("startup_failed type=%s", type(exc).__name__)
        guard.close()
        QMessageBox.critical(None, "Błąd uruchamiania", "Nie udało się uruchomić programu. Sprawdź środowisko i dziennik diagnostyczny.")
        return 2

    def exception_hook(kind, value, traceback):
        # Deliberately omit value and traceback: these may contain user content or credentials.
        logging.getLogger("quiz_assistant").error("unhandled_exception type=%s", kind.__name__)
        runtime.show_notification("Błąd aplikacji", "Operacja nie powiodła się. Sprawdź dziennik diagnostyczny.")
        runtime._cancel_all()
    sys.excepthook = exception_hook
    try:
        return application.exec()
    finally:
        guard.close()
