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
    interval_seconds: int

    @classmethod
    def from_toml(cls, config_path: str | Path = DEFAULT_CONFIG_PATH) -> "ApiSettings":
        """Load API-facing settings from the Axocare TOML configuration file."""
        path = Path(config_path)
        values = tomllib.loads(path.read_text(encoding="utf-8"))
        database = values.get("database", {})
        temperature = values.get("temperature", {})
        control = values.get("control", {})

        return cls(
            db_path=str(database.get("path", db.DEFAULT_DB_PATH)),
            target_c=float(temperature.get("target_c", 25.0)),
            cooling_on_c=float(temperature.get("cooling_on_c", 25.5)),
            cooling_off_c=float(temperature.get("cooling_off_c", 25.0)),
            interval_seconds=int(control.get("interval_seconds", 60)),
        )
