from quiz_assistant.geometry import (
    absolute_capture_rect,
    logical_rect_to_physical,
    region_is_valid,
)
from quiz_assistant.models import CaptureRegion, MonitorDescriptor


def monitor(
    *,
    left: int = 0,
    top: int = 0,
    width: int = 1920,
    height: int = 1080,
    ratio: float = 1.0,
) -> MonitorDescriptor:
    return MonitorDescriptor(
        monitor_id="DISPLAY1",
        label="test",
        mss_index=1,
        physical_left=left,
        physical_top=top,
        physical_width=width,
        physical_height=height,
        logical_left=0,
        logical_top=0,
        logical_width=round(width / ratio),
        logical_height=round(height / ratio),
        device_pixel_ratio=ratio,
        dpi=round(96 * ratio),
    )


def region_for(item: MonitorDescriptor) -> CaptureRegion:
    return CaptureRegion(
        monitor_id=item.monitor_id,
        x_px=100,
        y_px=50,
        width_px=800,
        height_px=500,
        configured_dpi=item.dpi,
        monitor_width_px=item.physical_width,
        monitor_height_px=item.physical_height,
    )


def test_logical_to_physical_for_supported_scaling_levels() -> None:
    assert logical_rect_to_physical(10, 20, 100, 80, 1.0) == (10, 20, 100, 80)
    assert logical_rect_to_physical(10, 20, 100, 80, 1.25) == (12, 25, 126, 100)
    assert logical_rect_to_physical(10, 20, 100, 80, 1.5) == (15, 30, 150, 120)
    assert logical_rect_to_physical(10, 20, 100, 80, 2.0) == (20, 40, 200, 160)


def test_absolute_rect_supports_monitor_left_of_primary() -> None:
    item = monitor(left=-2560, width=2560, height=1440, ratio=1.25)
    region = region_for(item)
    assert absolute_capture_rect(region, item) == {
        "left": -2460,
        "top": 50,
        "width": 800,
        "height": 500,
    }


def test_region_is_invalid_after_monitor_size_or_dpi_change() -> None:
    original = monitor()
    region = region_for(original)
    assert region_is_valid(region, original)
    assert not region_is_valid(region, monitor(width=2560, height=1440))
    assert not region_is_valid(region, monitor(ratio=1.25))


def test_region_must_remain_inside_monitor() -> None:
    item = monitor()
    bad = CaptureRegion(
        monitor_id=item.monitor_id,
        x_px=1800,
        y_px=0,
        width_px=200,
        height_px=200,
        configured_dpi=item.dpi,
        monitor_width_px=item.physical_width,
        monitor_height_px=item.physical_height,
    )
    assert not region_is_valid(bad, item)
