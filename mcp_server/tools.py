"""Typed MCP tool implementations for Axocare telemetry."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server import db

DEFAULT_DB_PATH = "axocare.db"
_db_path = DEFAULT_DB_PATH


def configure_database(db_path: str | Path) -> None:
    """Set the database used by subsequently invoked MCP tools."""
    global _db_path
    _db_path = str(db_path)


def get_current_status() -> dict[str, Any]:
    """Get the most recent aquarium temperature, cooling, and ambient status."""
    status = db.current_status(_db_path)
    if status is None:
        return {
            "data_available": False,
            "message": "No temperature readings are available yet.",
        }
    status["data_available"] = True
    status["age_seconds"] = _age_seconds(status["recorded_at"])
    return status


def get_recent_readings(minutes: int) -> dict[str, Any]:
    """Get chronological aquarium readings from the last 1 to 1,440 minutes."""
    _validate_range("minutes", minutes, minimum=1, maximum=1_440)
    return {"minutes": minutes, "readings": db.recent_readings(_db_path, minutes)}


def get_temperature_summary(hours: int) -> dict[str, Any]:
    """Get min, max, average, latest temperature and cooling use for 1 to 168 hours."""
    _validate_range("hours", hours, minimum=1, maximum=168)
    return {"hours": hours, **db.temperature_summary(_db_path, hours)}


def get_relay_events(hours: int) -> dict[str, Any]:
    """Get cooling relay state changes from the last 1 to 168 hours."""
    _validate_range("hours", hours, minimum=1, maximum=168)
    return {"hours": hours, "events": db.relay_events(_db_path, hours)}


def predict_temperature(horizon_minutes: int) -> dict[str, Any]:
    """Report prediction availability for a supported future horizon in minutes."""
    _validate_range("horizon_minutes", horizon_minutes, minimum=1, maximum=30)
    return {
        "available": False,
        "horizon_minutes": horizon_minutes,
        "message": (
            "Temperature prediction is unavailable because the local AI model "
            "has not been implemented and trained yet."
        ),
    }


def explain_temperature_trend(minutes: int) -> dict[str, Any]:
    """Summarize whether valid aquarium temperatures are rising, falling, or stable."""
    _validate_range("minutes", minutes, minimum=1, maximum=1_440)
    readings = db.recent_readings(_db_path, minutes)
    valid = [row for row in readings if row["aquarium_temperature_c"] is not None]
    if not valid:
        return {
            "minutes": minutes,
            "data_available": False,
            "message": "No valid aquarium temperature readings are available in this period.",
        }

    change = round(
        valid[-1]["aquarium_temperature_c"] - valid[0]["aquarium_temperature_c"],
        3,
    )
    trend = (
        "stable" if -0.1 <= change <= 0.1 else "rising" if change > 0 else "falling"
    )
    cooling_on_minutes = sum(1 for row in readings if row["cooling_on"])
    cooling_percent = round(cooling_on_minutes / len(readings) * 100, 1) if readings else 0.0
    return {
        "minutes": minutes,
        "data_available": True,
        "trend": trend,
        "temperature_change_c": change,
        "cooling_on_percent": cooling_percent,
        "summary": _trend_summary(trend, minutes, cooling_percent),
    }


def _validate_range(name: str, value: int, *, minimum: int, maximum: int) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.")


def _age_seconds(recorded_at: str) -> int | None:
    try:
        timestamp = datetime.fromisoformat(recorded_at.removesuffix("Z")).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return max(0, int((datetime.now(timezone.utc) - timestamp).total_seconds()))


def _trend_summary(trend: str, minutes: int, cooling_percent: float) -> str:
    description = {
        "stable": "remained nearly stable",
        "rising": "risen",
        "falling": "fallen",
    }[trend]
    return (
        f"The aquarium temperature has {description} over the last {minutes} minutes. "
        f"The cooling system was active for about {cooling_percent}% of the period."
    )
