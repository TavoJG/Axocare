"""Read-only SQLite queries used by the Axocare MCP tools."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def current_status(db_path: str | Path) -> dict[str, Any] | None:
    """Return the newest persisted aquarium reading, if one exists."""
    with _connect_readonly(db_path) as conn:
        row = conn.execute(
            """
            SELECT recorded_at, temperature_c, relay_on, room_temperature,
                   aht20_humidity_percent, bmp280_pressure_hpa, error,
                   ambient_error
            FROM temperature_readings
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return _status_row(row) if row is not None else None


def recent_readings(db_path: str | Path, minutes: int) -> list[dict[str, Any]]:
    """Return readings in the requested recent window, oldest first."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT recorded_at, temperature_c, relay_on, room_temperature,
                   aht20_humidity_percent, bmp280_pressure_hpa
            FROM temperature_readings
            WHERE recorded_at >= datetime('now', ?)
            ORDER BY recorded_at ASC, id ASC
            """,
            (f"-{minutes} minutes",),
        ).fetchall()
    return [_reading_row(row) for row in rows]


def temperature_summary(db_path: str | Path, hours: int) -> dict[str, Any]:
    """Return aggregate temperature and cooling data for a recent window."""
    with _connect_readonly(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS reading_count,
                COUNT(temperature_c) AS sample_count,
                MIN(temperature_c) AS min_temperature_c,
                MAX(temperature_c) AS max_temperature_c,
                AVG(temperature_c) AS avg_temperature_c,
                SUM(CASE WHEN relay_on = 1 THEN 1 ELSE 0 END) AS cooling_on_minutes
            FROM temperature_readings
            WHERE recorded_at >= datetime('now', ?)
            """,
            (f"-{hours} hours",),
        ).fetchone()
        latest = conn.execute(
            """
            SELECT temperature_c
            FROM temperature_readings
            WHERE recorded_at >= datetime('now', ?) AND temperature_c IS NOT NULL
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
            """,
            (f"-{hours} hours",),
        ).fetchone()

    reading_count = int(row["reading_count"])
    cooling_on_minutes = int(row["cooling_on_minutes"] or 0)
    return {
        "reading_count": reading_count,
        "sample_count": int(row["sample_count"]),
        "min_temperature_c": _rounded(row["min_temperature_c"]),
        "max_temperature_c": _rounded(row["max_temperature_c"]),
        "avg_temperature_c": _rounded(row["avg_temperature_c"]),
        "latest_temperature_c": _rounded(latest["temperature_c"]) if latest else None,
        "cooling_on_minutes": cooling_on_minutes,
        "cooling_on_percent": round(cooling_on_minutes / reading_count * 100, 1)
        if reading_count
        else 0.0,
    }


def relay_events(db_path: str | Path, hours: int) -> list[dict[str, Any]]:
    """Return cooling state transitions in the requested recent window."""
    with _connect_readonly(db_path) as conn:
        rows = conn.execute(
            """
            SELECT recorded_at, relay_on, reason, temperature_c
            FROM relay_events
            WHERE recorded_at >= datetime('now', ?)
            ORDER BY recorded_at ASC, id ASC
            """,
            (f"-{hours} hours",),
        ).fetchall()
    return [
        {
            "recorded_at": _iso_timestamp(row["recorded_at"]),
            "relay_on": bool(row["relay_on"]),
            "reason": row["reason"],
            "temperature_c": row["temperature_c"],
        }
        for row in rows
    ]


def _connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).expanduser().resolve()
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _status_row(row: sqlite3.Row) -> dict[str, Any]:
    result = _reading_row(row)
    result["sensor_error"] = row["error"]
    result["ambient_error"] = row["ambient_error"]
    return result


def _reading_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "recorded_at": _iso_timestamp(row["recorded_at"]),
        "aquarium_temperature_c": row["temperature_c"],
        "cooling_on": bool(row["relay_on"]),
        "room_temperature_c": row["room_temperature"],
        "humidity_percent": row["aht20_humidity_percent"],
        "pressure_hpa": row["bmp280_pressure_hpa"],
    }


def _iso_timestamp(value: str) -> str:
    """Render SQLite's UTC timestamp consistently for MCP clients."""
    return value if "T" in value else f"{value.replace(' ', 'T')}Z"


def _rounded(value: float | None) -> float | None:
    """Avoid exposing SQLite floating-point representation noise to clients."""
    return round(value, 3) if value is not None else None
