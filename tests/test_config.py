from pathlib import Path

from PySide6.QtCore import QSettings

from quiz_assistant.config import SettingsStore
from quiz_assistant.models import ApiConfig, CaptureRegion, HotkeyAction, PanelPosition


def store_for(tmp_path: Path) -> SettingsStore:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.clear()
    return SettingsStore(settings)


def test_region_and_panel_position_round_trip(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    region = CaptureRegion("DISPLAY1", 10, 20, 300, 200, 120, 1920, 1080)
    position = PanelPosition("DISPLAY1", 1400, 24)
    store.save_region(region)
    store.save_panel_position(position)
    assert store.load_region() == region
    assert store.load_panel_position() == position


def test_default_shortcuts_and_round_trip(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    defaults = store.load_shortcuts()
    assert defaults[HotkeyAction.ANALYZE] == "Ctrl+M"
    assert defaults[HotkeyAction.TOGGLE_OVERLAY] == "Ctrl+B"
    changed = dict(defaults)
    changed[HotkeyAction.ANALYZE] = "Ctrl+F9"
    store.save_shortcuts(changed)
    assert store.load_shortcuts() == changed


def test_old_toggle_shortcut_is_migrated(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "old-settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("hotkeys/toggle_overlay", "Ctrl+Shift+M")
    store = SettingsStore(settings)

    shortcuts = store.load_shortcuts()

    assert shortcuts[HotkeyAction.TOGGLE_OVERLAY] == "Ctrl+B"
    assert settings.value("hotkeys/toggle_overlay") == "Ctrl+B"


def test_api_config_round_trip(tmp_path: Path) -> None:
    store = store_for(tmp_path)
    config = ApiConfig(
        model="gpt-6.1-sol",
        reasoning_effort="low",
        image_detail="high",
        max_output_tokens=3000,
        deadline_seconds=15.0,
        session_budget_usd=1.25,
    )
    store.save_api_config(config)
    assert store.load_api_config() == config


def test_old_default_profile_migrates_without_raising_budget(tmp_path):
    store = store_for(tmp_path)
    s = store._settings
    for key, value in {"model": "gpt-6-luna", "reasoning_effort": "none", "max_output_tokens": 1500,
                       "deadline_seconds": 12, "session_budget_usd": .12}.items():
        s.setValue(f"api/{key}", value)
    assert store.load_api_config() == ApiConfig(session_budget_usd=.12)


def test_settings_never_store_api_key(tmp_path):
    store = store_for(tmp_path)
    store.save_api_config(ApiConfig())
    assert not any("key" in key.lower() or "secret" in key.lower() for key in store._settings.allKeys())


def test_corrupt_model_preserves_budget(tmp_path):
    store = store_for(tmp_path)
    store._settings.setValue("api/model", "unknown-model")
    store._settings.setValue("api/session_budget_usd", .03)
    store._settings.setValue("api/profile_version", "broken")
    assert store.load_api_config().session_budget_usd == .03
