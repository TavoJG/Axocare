from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import db as axocare_db
from mcp_server import tools


def test_current_status_and_recent_readings(tmp_path: Path) -> None:
    db_path = _seed_database(tmp_path)
    tools.configure_database(db_path)

    status = tools.get_current_status()
    recent = tools.get_recent_readings(60)

    assert status["data_available"] is True
    assert status["aquarium_temperature_c"] == 19.4
    assert status["cooling_on"] is True
    assert status["room_temperature_c"] == 24.8
    assert status["sensor_error"] is None
    assert status["ambient_error"] == "ambient sensor unavailable"
    assert status["age_seconds"] is not None
    assert [row["aquarium_temperature_c"] for row in recent["readings"]] == [19.2, 19.4]


def test_summary_events_and_trend(tmp_path: Path) -> None:
    db_path = _seed_database(tmp_path)
    tools.configure_database(db_path)

    summary = tools.get_temperature_summary(24)
    events = tools.get_relay_events(24)
    trend = tools.explain_temperature_trend(60)

    assert summary == {
        "hours": 24,
        "reading_count": 2,
        "sample_count": 2,
        "min_temperature_c": 19.2,
        "max_temperature_c": 19.4,
        "avg_temperature_c": 19.3,
        "latest_temperature_c": 19.4,
        "cooling_on_minutes": 1,
        "cooling_on_percent": 50.0,
    }
    assert len(events["events"]) == 1
    assert events["events"][0]["relay_on"] is True
    assert trend["trend"] == "rising"
    assert trend["temperature_change_c"] == 0.2
    assert trend["cooling_on_percent"] == 50.0


def test_empty_and_invalid_data_handling(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    axocare_db.migrate(db_path)
    tools.configure_database(db_path)

    assert tools.get_current_status() == {
        "data_available": False,
        "message": "No temperature readings are available yet.",
    }
    assert tools.explain_temperature_trend(60) == {
        "minutes": 60,
        "data_available": False,
        "message": "No valid aquarium temperature readings are available in this period.",
    }
    assert tools.get_temperature_summary(24)["sample_count"] == 0
    assert tools.get_temperature_summary(24)["latest_temperature_c"] is None

    with pytest.raises(ValueError, match="minutes must be an integer between 1 and 1440"):
        tools.get_recent_readings(0)
    with pytest.raises(ValueError, match="hours must be an integer between 1 and 168"):
        tools.get_relay_events(169)


def test_prediction_is_explicitly_unavailable(tmp_path: Path) -> None:
    tools.configure_database(tmp_path / "unused.db")

    assert tools.predict_temperature(15) == {
        "available": False,
        "horizon_minutes": 15,
        "message": "Temperature prediction is unavailable because the local AI model has not been implemented and trained yet.",
    }


def test_server_registers_the_expected_tools() -> None:
    pytest.importorskip("mcp")
    from mcp_server.server import mcp

    registered = set(mcp._tool_manager._tools)
    assert registered == {
        "get_current_status",
        "get_recent_readings",
        "get_temperature_summary",
        "get_relay_events",
        "predict_temperature",
        "explain_temperature_trend",
    }


def _seed_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "axocare.db"
    axocare_db.migrate(db_path)
    now = datetime.now(timezone.utc)
    _insert_temperature(
        db_path,
        recorded_at=now - timedelta(minutes=20),
        temperature_c=19.2,
        relay_on=False,
        ambient_error=None,
    )
    _insert_temperature(
        db_path,
        recorded_at=now - timedelta(minutes=5),
        temperature_c=19.4,
        relay_on=True,
        ambient_error="ambient sensor unavailable",
    )
    with axocare_db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO relay_events (recorded_at, relay_on, reason, temperature_c)
            VALUES (?, ?, ?, ?)
            """,
            (_sqlite_utc(now - timedelta(minutes=5)), 1, "temperature_above_threshold", 19.4),
        )
        conn.commit()
    return db_path


def _insert_temperature(
    db_path: Path,
    *,
    recorded_at: datetime,
    temperature_c: float,
    relay_on: bool,
    ambient_error: str | None,
) -> None:
    with axocare_db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO temperature_readings (
                recorded_at, temperature_c, relay_on, room_temperature,
                aht20_humidity_percent, bmp280_pressure_hpa, ambient_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _sqlite_utc(recorded_at),
                temperature_c,
                int(relay_on),
                24.8,
                48.2,
                1012.4,
                ambient_error,
            ),
        )
        conn.commit()


def _sqlite_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
