from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

from quiz_assistant.models import HotkeyAction


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

_MODIFIERS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "meta": MOD_WIN,
    "win": MOD_WIN,
}

_NAMED_KEYS = {
    "SPACE": 0x20,
    "TAB": 0x09,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
}


def parse_hotkey_sequence(sequence: str) -> tuple[int, int]:
    parts = [part.strip() for part in sequence.split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("Skrót musi zawierać modyfikator i klawisz.")

    modifiers = MOD_NOREPEAT
    for modifier in parts[:-1]:
        value = _MODIFIERS.get(modifier.casefold())
        if value is None:
            raise ValueError(f"Nieobsługiwany modyfikator: {modifier}")
        modifiers |= value

    key_name = parts[-1].upper()
    if len(key_name) == 1 and key_name in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        virtual_key = ord(key_name)
    elif key_name.startswith("F") and key_name[1:].isdigit():
        number = int(key_name[1:])
        if not 1 <= number <= 24:
            raise ValueError("Obsługiwane są klawisze F1-F24.")
        virtual_key = 0x70 + number - 1
    elif key_name in _NAMED_KEYS:
        virtual_key = _NAMED_KEYS[key_name]
    else:
        raise ValueError(f"Nieobsługiwany klawisz: {parts[-1]}")
    return modifiers, virtual_key


class _NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt API
        if sys.platform != "win32":
            return False, 0
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            self._callback(int(msg.wParam))
            return True, 0
        return False, 0


class HotkeyService(QObject):
    triggered = Signal(object)

    _IDS = {
        HotkeyAction.ANALYZE: 0x5101,
        HotkeyAction.ADD_FRAME: 0x5104,
        HotkeyAction.TOGGLE_OVERLAY: 0x5102,
        HotkeyAction.CANCEL: 0x5103,
    }

    def __init__(self, application, user32=None) -> None:
        super().__init__()
        self._application = application
        self._user32 = user32 or (ctypes.windll.user32 if sys.platform == "win32" else None)
        if user32 is None and self._user32 is not None:
            self._user32.RegisterHotKey.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                wintypes.UINT,
                wintypes.UINT,
            ]
            self._user32.RegisterHotKey.restype = wintypes.BOOL
            self._user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self._user32.UnregisterHotKey.restype = wintypes.BOOL
        self._registered: dict[int, HotkeyAction] = {}
        self._filter = _NativeHotkeyFilter(self._dispatch)
        self._application.installNativeEventFilter(self._filter)

    def register(self, shortcuts: dict[HotkeyAction, str]) -> tuple[bool, str]:
        self.unregister_all()
        if sys.platform != "win32":
            return False, "Globalne skróty są obsługiwane wyłącznie w Windows."

        parsed: dict[HotkeyAction, tuple[int, int]] = {}
        try:
            for action, sequence in shortcuts.items():
                parsed[action] = parse_hotkey_sequence(sequence)
        except ValueError as exc:
            return False, str(exc)

        if len(set(parsed.values())) != len(parsed):
            return False, "Każda akcja musi mieć inny skrót."

        for action, (modifiers, virtual_key) in parsed.items():
            identifier = self._IDS[action]
            if not self._user32.RegisterHotKey(None, identifier, modifiers, virtual_key):
                self.unregister_all()
                return False, f"Nie udało się zarejestrować skrótu: {shortcuts[action]}"
            self._registered[identifier] = action
        return True, ""

    def unregister_all(self) -> None:
        if sys.platform == "win32":
            for identifier in tuple(self._registered):
                self._user32.UnregisterHotKey(None, identifier)
        self._registered.clear()

    def _dispatch(self, identifier: int) -> None:
        action = self._registered.get(identifier)
        if action is not None:
            self.triggered.emit(action)

    def close(self) -> None:
        self.unregister_all()
        self._application.removeNativeEventFilter(self._filter)
