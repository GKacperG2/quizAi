from __future__ import annotations

import mss
from PySide6.QtGui import QGuiApplication

from quiz_assistant.models import MonitorDescriptor


def enumerate_monitors() -> list[MonitorDescriptor]:
    """Pair Qt screens with MSS physical monitor rectangles.

    Qt provides the UI-space geometry and device pixel ratio. MSS provides the
    physical pixel rectangle used for capture. Pairing prefers physical size
    and falls back to enumeration order when monitors are otherwise identical.
    """
    qt_screens = list(QGuiApplication.screens())
    with mss.mss() as session:
        mss_monitors = [dict(item) for item in session.monitors[1:]]

    unused = set(range(len(mss_monitors)))
    result: list[MonitorDescriptor] = []

    for qt_index, screen in enumerate(qt_screens):
        geometry = screen.geometry()
        ratio = float(screen.devicePixelRatio())
        expected_width = round(geometry.width() * ratio)
        expected_height = round(geometry.height() * ratio)

        candidates = [
            index
            for index in unused
            if abs(int(mss_monitors[index]["width"]) - expected_width) <= 2
            and abs(int(mss_monitors[index]["height"]) - expected_height) <= 2
        ]
        if not candidates and qt_index in unused:
            candidates = [qt_index]
        if not candidates:
            continue

        mss_index = min(candidates)
        unused.remove(mss_index)
        physical = mss_monitors[mss_index]
        monitor_id = screen.name() or f"DISPLAY-{mss_index + 1}"
        result.append(
            MonitorDescriptor(
                monitor_id=monitor_id,
                label=(
                    f"{monitor_id} — {physical['width']}×{physical['height']} px "
                    f"({round(ratio * 100)}%)"
                ),
                mss_index=mss_index + 1,
                physical_left=int(physical["left"]),
                physical_top=int(physical["top"]),
                physical_width=int(physical["width"]),
                physical_height=int(physical["height"]),
                logical_left=geometry.left(),
                logical_top=geometry.top(),
                logical_width=geometry.width(),
                logical_height=geometry.height(),
                device_pixel_ratio=ratio,
                dpi=round(96 * ratio),
            )
        )
    return result


def find_monitor(
    monitors: list[MonitorDescriptor], monitor_id: str
) -> MonitorDescriptor | None:
    return next((item for item in monitors if item.monitor_id == monitor_id), None)
