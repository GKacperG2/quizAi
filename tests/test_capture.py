from pathlib import Path

from quiz_assistant.capture import CaptureService
from quiz_assistant.models import CaptureRegion, MonitorDescriptor


class FakeShot:
    width = 4
    height = 3
    bgra = bytes(range(48))


class FakeMss:
    def __init__(self) -> None:
        self.requested = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def grab(self, requested):
        self.requested = requested
        return FakeShot()


def fixtures() -> tuple[CaptureRegion, MonitorDescriptor]:
    monitor = MonitorDescriptor(
        monitor_id="DISPLAY1",
        label="test",
        mss_index=1,
        physical_left=-100,
        physical_top=20,
        physical_width=1000,
        physical_height=800,
        logical_left=0,
        logical_top=0,
        logical_width=1000,
        logical_height=800,
        device_pixel_ratio=1,
        dpi=96,
    )
    region = CaptureRegion("DISPLAY1", 10, 15, 4, 3, 96, 1000, 800)
    return region, monitor


def test_capture_returns_memory_only_frame(tmp_path: Path) -> None:
    fake = FakeMss()
    service = CaptureService(lambda: fake)
    region, monitor = fixtures()
    before = set(tmp_path.iterdir())

    frame = service.capture(region, monitor)

    assert frame.width == 4
    assert frame.height == 3
    assert frame.bgra_bytes == FakeShot.bgra
    assert len(frame.sha256) == 64
    assert fake.requested == {"left": -90, "top": 35, "width": 4, "height": 3}
    assert set(tmp_path.iterdir()) == before
