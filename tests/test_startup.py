import importlib.machinery
import importlib.util
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QMenu
from quiz_assistant.diagnostics import configure_logging
from quiz_assistant.config import SettingsStore
from quiz_assistant.models import AppState


class FakeHotkeys(QObject):
    triggered = Signal(object)
    def __init__(self, app):
        super().__init__()
        self.closed = False
    def register(self, shortcuts):
        return True, ""
    def close(self):
        self.closed = True


class FakeGuard(QObject):
    activation_requested = Signal()
    def close(self):
        pass


class FakeTray(QObject):
    activated = Signal(object)
    def __init__(self, *args):
        super().__init__()
    def __getattr__(self, name):
        return lambda *args: None


def test_runtime_starts_without_key_and_shutdown_is_clean(qt_app, monkeypatch, tmp_path):
    from quiz_assistant import app as module
    store = SettingsStore(QSettings(str(tmp_path / "runtime.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(module, "SettingsStore", lambda: store)
    monkeypatch.setattr(module, "enumerate_monitors", lambda: [])
    monkeypatch.setattr(module, "ApiKeyStore", lambda: SimpleNamespace(get_key=lambda: None))
    monkeypatch.setattr(module, "HotkeyService", FakeHotkeys)
    monkeypatch.setattr(module, "QSystemTrayIcon", FakeTray)
    monkeypatch.setattr(module.QuizAssistantRuntime, "show_notification", lambda *args: None)
    quits = []
    monkeypatch.setattr(qt_app, "quit", lambda: quits.append(True))
    runtime = module.QuizAssistantRuntime(qt_app, FakeGuard(), tmp_path / "test.log")
    assert runtime._main.isVisible()
    assert runtime._controller.state is AppState.UNCONFIGURED
    runtime._main.close()
    runtime._guard.activation_requested.emit()
    assert runtime._main.isVisible()
    runtime.shutdown()
    assert runtime._hotkeys.closed and quits == [True]


def test_diagnostic_logger_rotates_without_http_loggers(tmp_path):
    path = configure_logging(tmp_path)
    logger = logging.getLogger("quiz_assistant")
    handler = logger.handlers[0]
    assert handler.backupCount == 3 and handler.maxBytes == 512_000
    logger.info("test_event generation=%s", 1)
    handler.flush()
    assert "test_event generation=1" in path.read_text(encoding="utf-8")
    assert logger.propagate is False
    assert not logging.getLogger("httpx").handlers
    handler.close()
    logger.removeHandler(handler)


def test_launcher_import_failure_is_visible_and_does_not_leak_exception(monkeypatch):
    import builtins
    import ctypes
    path = Path(__file__).resolve().parents[1] / "launch.pyw"
    loader = importlib.machinery.SourceFileLoader("test_launcher", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    actual_import = builtins.__import__
    def failing_import(name, *args, **kwargs):
        if name == "quiz_assistant.app":
            raise ImportError("secret-text-not-for-dialog")
        return actual_import(name, *args, **kwargs)
    messages = []
    monkeypatch.setattr(builtins, "__import__", failing_import)
    monkeypatch.setattr(ctypes.windll.user32, "MessageBoxW", lambda *args: messages.append(args))
    assert module.launch() == 2
    assert len(messages) == 1
    assert "pip install" in messages[0][1]
    assert "secret-text" not in messages[0][1]


def test_launcher_paths_are_relative_to_itself_not_terminal():
    root = Path(__file__).resolve().parents[1]
    text = (root / "Uruchom_Asystenta.cmd").read_text()
    assert '%~dp0.venv\\Scripts\\pythonw.exe' in text
    assert 'cd /d "%~dp0"' in text
    assert "activate" not in text
