"""Configuration loading for the Axocare API."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel

import db

DEFAULT_CONFIG_PATH = "config.toml"
DEFAULT_HISTORY_MINUTES = 60
DEFAULT_LIMIT = 50


class ApiSettings(BaseModel):
    """Runtime settings needed by the API."""

    db_path: str
    target_c: float
    cooling_on_c: float
    cooling_off_c: float
    notification_threshold_c: float | None
    interval_seconds: int
    camera_enabled: bool = False
    camera_device: str = "0"
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 15
    camera_jpeg_quality: int = 80

    @classmethod
    def from_toml(cls, config_path: str | Path = DEFAULT_CONFIG_PATH) -> "ApiSettings":
        """Load API-facing settings from the Axocare TOML configuration file."""
        path = Path(config_path)
        values = tomllib.loads(path.read_text(encoding="utf-8"))
        database = values.get("database", {})
        temperature = values.get("temperature", {})
        control = values.get("control", {})
        camera = values.get("camera", {})

        return cls(
            db_path=str(database.get("path", db.DEFAULT_DB_PATH)),
            target_c=float(temperature.get("target_c", 25.0)),
            cooling_on_c=float(temperature.get("cooling_on_c", 25.5)),
            cooling_off_c=float(temperature.get("cooling_off_c", 25.0)),
            notification_threshold_c=_optional_float(
                temperature.get("notification_threshold_c")
            ),
            interval_seconds=int(control.get("interval_seconds", 60)),
            camera_enabled=bool(camera.get("enabled", False)),
            camera_device=str(camera.get("device", "0")),
            camera_width=int(camera.get("width", 640)),
            camera_height=int(camera.get("height", 480)),
            camera_fps=int(camera.get("fps", 15)),
            camera_jpeg_quality=int(camera.get("jpeg_quality", 80)),
        )


def _optional_float(value) -> float | None:
    """Return a float for configured values while treating blanks as disabled."""
    if value is None or value == "":
        return None
    return float(value)
