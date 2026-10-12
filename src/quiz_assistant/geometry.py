from __future__ import annotations

import math

from quiz_assistant.models import CaptureRegion, MonitorDescriptor


def logical_rect_to_physical(
    x: float,
    y: float,
    width: float,
    height: float,
    device_pixel_ratio: float,
) -> tuple[int, int, int, int]:
    """Convert a monitor-local logical rectangle without dropping edge pixels."""
    if device_pixel_ratio <= 0:
        raise ValueError("device_pixel_ratio must be positive")
    if width <= 0 or height <= 0:
        raise ValueError("selection must have a positive size")

    left = math.floor(x * device_pixel_ratio)
    top = math.floor(y * device_pixel_ratio)
    right = math.ceil((x + width) * device_pixel_ratio)
    bottom = math.ceil((y + height) * device_pixel_ratio)
    return left, top, right - left, bottom - top


def region_is_valid(region: CaptureRegion | None, monitor: MonitorDescriptor | None) -> bool:
    if region is None or monitor is None:
        return False
    if region.monitor_id != monitor.monitor_id:
        return False
    if region.width_px <= 0 or region.height_px <= 0:
        return False
    if region.x_px < 0 or region.y_px < 0:
        return False
    if region.x_px + region.width_px > monitor.physical_width:
        return False
    if region.y_px + region.height_px > monitor.physical_height:
        return False
    if region.monitor_width_px != monitor.physical_width:
        return False
    if region.monitor_height_px != monitor.physical_height:
        return False
    return abs(region.configured_dpi - monitor.dpi) <= 1


def absolute_capture_rect(
    region: CaptureRegion,
    monitor: MonitorDescriptor,
) -> dict[str, int]:
    if not region_is_valid(region, monitor):
        raise ValueError("Capture region no longer matches its monitor")
    return {
        "left": monitor.physical_left + region.x_px,
        "top": monitor.physical_top + region.y_px,
        "width": region.width_px,
        "height": region.height_px,
    }
