import pytest

from quiz_assistant.models import DEFAULT_SHORTCUTS, HotkeyAction
from quiz_assistant.platform.windows.hotkeys import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    HotkeyService,
    parse_hotkey_sequence,
)


class FakeApplication:
    def installNativeEventFilter(self, _filter):
        pass

    def removeNativeEventFilter(self, _filter):
        pass


class FakeUser32:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.registered = []
        self.unregistered = []

    def RegisterHotKey(self, hwnd, identifier, modifiers, key):
        del hwnd
        self.calls += 1
        if self.fail_on_call == self.calls:
            return 0
        self.registered.append((identifier, modifiers, key))
        return 1

    def UnregisterHotKey(self, hwnd, identifier):
        del hwnd
        self.unregistered.append(identifier)
        return 1


def test_parse_default_sequences() -> None:
    assert parse_hotkey_sequence("Ctrl+M") == (MOD_CONTROL | MOD_NOREPEAT, ord("M"))
    assert parse_hotkey_sequence("Ctrl+B") == (MOD_CONTROL | MOD_NOREPEAT, ord("B"))
    assert parse_hotkey_sequence("Ctrl+Shift+M") == (
        MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT,
        ord("M"),
    )
    assert parse_hotkey_sequence("Ctrl+Alt+M") == (
        MOD_CONTROL | MOD_ALT | MOD_NOREPEAT,
        ord("M"),
    )


@pytest.mark.parametrize("sequence", ["M", "Ctrl+Ł", "Ctrl+F25", "Hyper+M"])
def test_rejects_unsupported_sequences(sequence: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey_sequence(sequence)


def test_registration_rolls_back_after_conflict() -> None:
    user32 = FakeUser32(fail_on_call=2)
    service = HotkeyService(FakeApplication(), user32=user32)
    ok, message = service.register(DEFAULT_SHORTCUTS)
    assert not ok
    assert "Nie udało się" in message
    assert len(user32.unregistered) == 1
    service.close()


def test_duplicate_shortcuts_are_rejected_before_os_registration() -> None:
    user32 = FakeUser32()
    service = HotkeyService(FakeApplication(), user32=user32)
    duplicate = {action: "Ctrl+M" for action in HotkeyAction}
    ok, message = service.register(duplicate)
    assert not ok
    assert "inny skrót" in message
    assert user32.registered == []
    service.close()
