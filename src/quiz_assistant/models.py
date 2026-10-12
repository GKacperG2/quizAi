from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import math
import time
from dataclasses import field


class AppState(Enum):
    UNCONFIGURED = auto()
    READY = auto()
    PAUSED = auto()
    CAPTURING = auto()
    REQUESTING = auto()
    VALIDATING = auto()
    SHOWING_RESULT = auto()
    UNCERTAIN = auto()
    TIMEOUT = auto()
    ERROR = auto()


class HotkeyAction(Enum):
    ANALYZE = auto()
    ADD_FRAME = auto()
    TOGGLE_OVERLAY = auto()
    CANCEL = auto()


@dataclass(frozen=True, slots=True)
class MonitorDescriptor:
    monitor_id: str
    label: str
    mss_index: int
    physical_left: int
    physical_top: int
    physical_width: int
    physical_height: int
    logical_left: int
    logical_top: int
    logical_width: int
    logical_height: int
    device_pixel_ratio: float
    dpi: int


@dataclass(frozen=True, slots=True)
class CaptureRegion:
    monitor_id: str
    x_px: int
    y_px: int
    width_px: int
    height_px: int
    configured_dpi: int
    monitor_width_px: int
    monitor_height_px: int


@dataclass(frozen=True, slots=True)
class CaptureFrame:
    width: int
    height: int
    bgra_bytes: bytes
    captured_at: float
    sha256: str
    captured_wall_time: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PanelPosition:
    monitor_id: str
    x_logical: int
    y_logical: int


@dataclass(frozen=True, slots=True)
class ApiConfig:
    model: str = "gpt-6.1-sol"
    reasoning_effort: str = "medium"
    image_detail: str = "auto"
    max_output_tokens: int = 6000
    deadline_seconds: float = 20.0
    session_budget_usd: float = 0.50

    def __post_init__(self) -> None:
        if self.model not in ("gpt-6.1-sol", "gpt-6-luna", "gpt-6-astra"):
            raise ValueError("Nieobsługiwany model.")
        efforts = ("low", "medium", "high", "xhigh", "max")
        if self.reasoning_effort not in efforts + (("none",) if self.model == "gpt-6-luna" else ()):
            raise ValueError("Ten model nie obsługuje wybranego poziomu rozumowania.")
        if self.image_detail not in ("auto", "high", "low"):
            raise ValueError("Nieprawidłowa szczegółowość obrazu.")
        if not 128 <= self.max_output_tokens <= 16000:
            raise ValueError("Limit wyjścia musi wynosić 128–16000 tokenów.")
        if not math.isfinite(self.deadline_seconds) or not 3 <= self.deadline_seconds <= 60:
            raise ValueError("Limit czasu musi wynosić 3–60 sekund.")
        if not math.isfinite(self.session_budget_usd) or not 0.01 <= self.session_budget_usd <= 100:
            raise ValueError("Budżet musi wynosić 0,01–100 USD.")


@dataclass(frozen=True, slots=True)
class OverlayAppearance:
    theme: str = "dark"
    opacity: int = 95
    brightness: int = 50
    contrast: int = 100
    font_size: int = 16
    width: int = 420

    def __post_init__(self) -> None:
        if self.theme not in ("dark", "light"):
            raise ValueError("Nieprawidłowy motyw.")
        for name, low, high in (
            ("opacity", 50, 100), ("brightness", 0, 100), ("contrast", 0, 100),
            ("font_size", 12, 24), ("width", 320, 720),
        ):
            if not low <= getattr(self, name) <= high:
                raise ValueError(f"Nieprawidłowy parametr wyglądu: {name}")


DEFAULT_SHORTCUTS: dict[HotkeyAction, str] = {
    HotkeyAction.ANALYZE: "Ctrl+M",
    HotkeyAction.ADD_FRAME: "Ctrl+Shift+M",
    HotkeyAction.TOGGLE_OVERLAY: "Ctrl+B",
    HotkeyAction.CANCEL: "Ctrl+Alt+M",
}
