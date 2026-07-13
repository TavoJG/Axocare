"""SQLite access helpers for Axocare AI model training and prediction."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def load_temperature_history(db_path: str | Path) -> pd.DataFrame:
    """Load temperature history ordered chronologically for feature engineering."""
    path = Path(db_path).expanduser().resolve()
    with sqlite3.connect(path) as conn:
        frame = pd.read_sql_query(
            """
            SELECT
                id,
                recorded_at,
                temperature_c,
                relay_on,
                room_temperature,
                aht20_humidity_percent,
                bmp280_temperature_c,
                bmp280_pressure_hpa,
                error,
                ambient_error
            FROM temperature_readings
            ORDER BY recorded_at ASC, id ASC
            """,
            conn,
        )

    if frame.empty:
        return frame

    frame["recorded_at"] = pd.to_datetime(frame["recorded_at"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["recorded_at"]).copy()

    numeric_columns = [
        "temperature_c",
        "relay_on",
        "room_temperature",
        "aht20_humidity_percent",
        "bmp280_temperature_c",
        "bmp280_pressure_hpa",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["relay_on"] = frame["relay_on"].fillna(0).astype(int)
    return frame.reset_index(drop=True)

