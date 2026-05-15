"""MJPEG camera streaming helpers."""

from __future__ import annotations

import time
from collections.abc import Iterator

from axocare_api.settings import ApiSettings

BOUNDARY = "frame"


class CameraUnavailableError(RuntimeError):
    """Raised when camera streaming cannot be started."""


class MjpegCameraStream:
    """Iterable MJPEG stream that owns one OpenCV capture."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        self.cv2 = _load_cv2()
        self.capture = self.cv2.VideoCapture(_device_value(settings.camera_device))
        if not self.capture.isOpened():
            raise CameraUnavailableError(
                f"Could not open camera device {settings.camera_device!r}"
            )

        self.capture.set(self.cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
        self.capture.set(self.cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
        self.capture.set(self.cv2.CAP_PROP_FPS, settings.camera_fps)

    def __iter__(self) -> Iterator[bytes]:
        frame_delay = 1 / max(self.settings.camera_fps, 1)
        encode_params = [
            int(self.cv2.IMWRITE_JPEG_QUALITY),
            min(max(self.settings.camera_jpeg_quality, 1), 100),
        ]

        try:
            while True:
                ok, frame = self.capture.read()
                if not ok:
                    time.sleep(frame_delay)
                    continue

                encoded_ok, buffer = self.cv2.imencode(".jpg", frame, encode_params)
                if not encoded_ok:
                    time.sleep(frame_delay)
                    continue

                jpg = buffer.tobytes()
                yield (
                    f"--{BOUNDARY}\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpg)}\r\n\r\n"
                ).encode("ascii") + jpg + b"\r\n"
                time.sleep(frame_delay)
        finally:
            self.capture.release()


def _load_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise CameraUnavailableError(
            "Camera streaming requires OpenCV. Install python3-opencv on the Pi."
        ) from exc
    return cv2


def _device_value(device: str) -> int | str:
    return int(device) if device.isdigit() else device
