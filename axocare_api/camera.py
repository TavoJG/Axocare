"""MJPEG camera streaming helpers."""

from __future__ import annotations

import time
from collections.abc import Iterator
from threading import Lock
from typing import Any

from axocare_api.settings import ApiSettings

BOUNDARY = "frame"


class CameraUnavailableError(RuntimeError):
    """Raised when camera streaming cannot be started."""


class MjpegCameraStream:
    """Iterable MJPEG stream that shares one OpenCV capture per camera."""

    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        self.closed = True
        self.cv2 = _load_cv2()
        self.shared_capture = _CapturePool.acquire(settings, self.cv2)
        self.closed = False

    def __iter__(self) -> Iterator[bytes]:
        frame_delay = 1 / max(self.settings.camera_fps, 1)
        encode_params = [
            int(self.cv2.IMWRITE_JPEG_QUALITY),
            min(max(self.settings.camera_jpeg_quality, 1), 100),
        ]

        try:
            while True:
                ok, frame = self.shared_capture.read()
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
            self.close()

    def close(self) -> None:
        """Release this stream's reference to the shared camera capture."""
        if self.closed:
            return
        self.closed = True
        _CapturePool.release(self.shared_capture)

    def __del__(self) -> None:
        self.close()


class _SharedCapture:
    """Thread-safe wrapper around one OpenCV capture."""

    def __init__(self, capture: Any) -> None:
        self.capture = capture
        self.lock = Lock()
        self.ref_count = 1

    def read(self):
        with self.lock:
            return self.capture.read()

    def release(self) -> None:
        with self.lock:
            self.capture.release()


class _CapturePool:
    """Keeps camera devices open once while one or more clients are streaming."""

    _captures: dict[tuple[int | str, int, int, int], _SharedCapture] = {}
    _lock = Lock()

    @classmethod
    def acquire(cls, settings: ApiSettings, cv2) -> _SharedCapture:
        key = cls._key(settings)
        with cls._lock:
            shared_capture = cls._captures.get(key)
            if shared_capture is not None:
                shared_capture.ref_count += 1
                return shared_capture

            capture = cv2.VideoCapture(key[0])
            if not capture.isOpened():
                capture.release()
                raise CameraUnavailableError(
                    f"Could not open camera device {settings.camera_device!r}"
                )

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.camera_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.camera_height)
            capture.set(cv2.CAP_PROP_FPS, settings.camera_fps)

            shared_capture = _SharedCapture(capture)
            cls._captures[key] = shared_capture
            return shared_capture

    @classmethod
    def release(cls, shared_capture: _SharedCapture) -> None:
        with cls._lock:
            shared_capture.ref_count -= 1
            if shared_capture.ref_count > 0:
                return

            for key, pooled_capture in list(cls._captures.items()):
                if pooled_capture is shared_capture:
                    del cls._captures[key]
                    break

        shared_capture.release()

    @staticmethod
    def _key(settings: ApiSettings) -> tuple[int | str, int, int, int]:
        return (
            _device_value(settings.camera_device),
            settings.camera_width,
            settings.camera_height,
            settings.camera_fps,
        )


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
