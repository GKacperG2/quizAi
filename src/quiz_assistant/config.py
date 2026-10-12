from __future__ import annotations

from dataclasses import asdict
import math

from PySide6.QtCore import QSettings

from quiz_assistant.models import (
    DEFAULT_SHORTCUTS,
    ApiConfig,
    CaptureRegion,
    HotkeyAction,
    PanelPosition,
    OverlayAppearance,
)


class SettingsStore:
    _SCHEMA_VERSION = 2

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings()

    def load_region(self) -> CaptureRegion | None:
        s = self._settings
        monitor_id = s.value("capture/monitor_id", "", str)
        if not monitor_id:
            return None
        try:
            return CaptureRegion(
                monitor_id=monitor_id,
                x_px=int(s.value("capture/x_px")),
                y_px=int(s.value("capture/y_px")),
                width_px=int(s.value("capture/width_px")),
                height_px=int(s.value("capture/height_px")),
                configured_dpi=int(s.value("capture/configured_dpi")),
                monitor_width_px=int(s.value("capture/monitor_width_px")),
                monitor_height_px=int(s.value("capture/monitor_height_px")),
            )
        except (TypeError, ValueError):
            return None

    def save_region(self, region: CaptureRegion) -> None:
        for field_name in (
            "monitor_id",
            "x_px",
            "y_px",
            "width_px",
            "height_px",
            "configured_dpi",
            "monitor_width_px",
            "monitor_height_px",
        ):
            self._settings.setValue(f"capture/{field_name}", getattr(region, field_name))
        self._settings.sync()

    def load_panel_position(self) -> PanelPosition | None:
        monitor_id = self._settings.value("panel/monitor_id", "", str)
        if not monitor_id:
            return None
        try:
            return PanelPosition(
                monitor_id=monitor_id,
                x_logical=int(self._settings.value("panel/x_logical")),
                y_logical=int(self._settings.value("panel/y_logical")),
            )
        except (TypeError, ValueError):
            return None

    def save_panel_position(self, position: PanelPosition) -> None:
        self._settings.setValue("panel/monitor_id", position.monitor_id)
        self._settings.setValue("panel/x_logical", position.x_logical)
        self._settings.setValue("panel/y_logical", position.y_logical)
        self._settings.sync()

    def load_shortcuts(self) -> dict[HotkeyAction, str]:
        shortcuts = {
            action: self._settings.value(
                f"hotkeys/{action.name.lower()}", default, str
            )
            for action, default in DEFAULT_SHORTCUTS.items()
        }
        try:
            schema_version = int(self._settings.value("settings/schema_version", 0))
        except (TypeError, ValueError):
            schema_version = 0
        if (
            schema_version < self._SCHEMA_VERSION
            and shortcuts[HotkeyAction.TOGGLE_OVERLAY] == "Ctrl+Shift+M"
        ):
            shortcuts[HotkeyAction.TOGGLE_OVERLAY] = "Ctrl+B"
            self._settings.setValue("hotkeys/toggle_overlay", "Ctrl+B")
        if schema_version < self._SCHEMA_VERSION:
            self._settings.setValue("settings/schema_version", self._SCHEMA_VERSION)
            self._settings.sync()
        return shortcuts

    def save_shortcuts(self, shortcuts: dict[HotkeyAction, str]) -> None:
        for action, sequence in shortcuts.items():
            self._settings.setValue(f"hotkeys/{action.name.lower()}", sequence)
        self._settings.sync()

    def load_api_config(self) -> ApiConfig:
        # Migrate only the old shipped profile, never custom settings or the budget.
        try:
            old_default = (int(self._settings.value("api/profile_version", 0)) < 3
                and self._settings.value("api/model", "", str) == "gpt-6-luna"
                and self._settings.value("api/reasoning_effort", "none", str) == "none"
                and int(self._settings.value("api/max_output_tokens", 1500)) == 1500
                and float(self._settings.value("api/deadline_seconds", 12.0)) == 12.0)
        except (TypeError, ValueError):
            old_default = False
        if old_default:
            self._settings.setValue("api/model", "gpt-6.1-sol")
            self._settings.setValue("api/reasoning_effort", "medium")
            self._settings.setValue("api/max_output_tokens", 6000)
            self._settings.setValue("api/deadline_seconds", 20.0)
        self._settings.setValue("api/profile_version", 3)
        model = self._settings.value("api/model", "gpt-6.1-sol", str)
        default_effort = "medium" if model == "gpt-6.1-sol" else "low"
        try:
            budget = float(self._settings.value("api/session_budget_usd", .5))
            if not math.isfinite(budget) or not .01 <= budget <= 100:
                budget = .01
        except (TypeError, ValueError):
            budget = .01
        try:
            return ApiConfig(
                model=model,
                reasoning_effort=self._settings.value(
                    "api/reasoning_effort", default_effort, str
                ),
                image_detail=self._settings.value("api/image_detail", "auto", str),
                max_output_tokens=int(
                    self._settings.value(
                        "api/max_output_tokens", 6000
                    )
                ),
                deadline_seconds=float(self._settings.value("api/deadline_seconds", 20.0)),
                session_budget_usd=budget,
            )
        except (TypeError, ValueError):
            return ApiConfig(session_budget_usd=budget)

    def save_api_config(self, config: ApiConfig) -> None:
        self._settings.setValue("api/profile_version", 3)
        for field_name in (
            "model",
            "reasoning_effort",
            "image_detail",
            "max_output_tokens",
            "deadline_seconds",
            "session_budget_usd",
        ):
            self._settings.setValue(f"api/{field_name}", getattr(config, field_name))
        self._settings.sync()

    def load_appearance(self) -> OverlayAppearance:
        defaults = asdict(OverlayAppearance())
        try:
            return OverlayAppearance(**{
                key: self._settings.value(f"appearance/{key}", value, type(value))
                for key, value in defaults.items()
            })
        except (TypeError, ValueError):
            return OverlayAppearance()

    def save_appearance(self, appearance: OverlayAppearance) -> None:
        for key, value in asdict(appearance).items():
            self._settings.setValue(f"appearance/{key}", value)
        self._settings.sync()
