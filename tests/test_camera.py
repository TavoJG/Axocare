from __future__ import annotations

import sys

from axocare_api.camera import MjpegCameraStream
from axocare_api.settings import ApiSettings


def test_mjpeg_streams_share_one_camera_capture(monkeypatch) -> None:
    fake_cv2 = _FakeCv2()
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)
    settings = _camera_settings()

    stream_one = MjpegCameraStream(settings)
    stream_two = MjpegCameraStream(settings)

    assert len(fake_cv2.captures) == 1
    capture = fake_cv2.captures[0]
    assert capture.device == 0

    iterator_one = iter(stream_one)
    iterator_two = iter(stream_two)
    assert next(iterator_one).startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert next(iterator_two).startswith(b"--frame\r\nContent-Type: image/jpeg")

    iterator_one.close()
    assert capture.release_count == 0

    iterator_two.close()
    assert capture.release_count == 1


def _camera_settings() -> ApiSettings:
    return ApiSettings(
        db_path=":memory:",
        target_c=18.0,
        cooling_on_c=18.6,
        cooling_off_c=18.0,
        notification_threshold_c=20.0,
        interval_seconds=60,
        camera_enabled=True,
        camera_device="0",
        camera_width=640,
        camera_height=480,
        camera_fps=15,
        camera_jpeg_quality=80,
    )


class _FakeCv2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5
    IMWRITE_JPEG_QUALITY = 1

    def __init__(self) -> None:
        self.captures: list[_FakeCapture] = []

    def VideoCapture(self, device):
        capture = _FakeCapture(device)
        self.captures.append(capture)
        return capture

    def imencode(self, extension: str, frame, params):
        assert extension == ".jpg"
        assert params == [self.IMWRITE_JPEG_QUALITY, 80]
        return True, _FakeBuffer(b"jpeg-" + frame)


class _FakeCapture:
    def __init__(self, device) -> None:
        self.device = device
        self.release_count = 0
        self.properties: dict[int, int] = {}

    def isOpened(self) -> bool:
        return True

    def set(self, prop: int, value: int) -> None:
        self.properties[prop] = value

    def read(self):
        return True, b"frame"

    def release(self) -> None:
        self.release_count += 1


class _FakeBuffer:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def tobytes(self) -> bytes:
        return self.value
