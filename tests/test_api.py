from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import db
from axocare_api.app import create_app


def test_health_and_empty_current_reading(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"

    with TestClient(create_app(_write_config(tmp_path, db_path))) as client:
        health = client.get("/api/health")
        current = client.get("/api/current")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "db_path": str(db_path)}
    assert current.status_code == 200
    assert current.json() == {"reading": None, "db_path": str(db_path)}


def test_dashboard_returns_current_history_and_relay_events(tmp_path: Path) -> None:
    db_path = tmp_path / "seeded.db"
    config_path = _write_config(tmp_path, db_path)
    db.migrate(db_path)
    _insert_temperature(
        db_path,
        recorded_at="2000-01-01 00:00:00",
        temperature_c=17.5,
        relay_on=False,
        sensor_id="old-sensor",
    )
    _insert_temperature(
        db_path,
        recorded_at="2999-01-01 00:00:00",
        temperature_c=18.7,
        relay_on=True,
        sensor_id="test-sensor",
    )
    _insert_relay_event(
        db_path,
        recorded_at="2999-01-01 00:01:00",
        relay_on=True,
        reason="temperature_above_cooling_threshold",
        temperature_c=18.7,
    )

    with TestClient(create_app(config_path)) as client:
        response = client.get("/api/dashboard?span_minutes=60&event_limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["db_path"] == str(db_path)
    assert payload["span_minutes"] == 60
    assert payload["settings"] == {
        "db_path": str(db_path),
        "target_c": 18.0,
        "cooling_on_c": 18.6,
        "cooling_off_c": 18.0,
        "interval_seconds": 60,
    }
    assert payload["current"] == {
        "id": 2,
        "recorded_at": "2999-01-01T00:00:00Z",
        "temperature_c": 18.7,
        "relay_on": True,
        "sensor_id": "test-sensor",
        "error": None,
    }
    assert payload["readings"] == [payload["current"]]
    assert payload["relay_events"] == [
        {
            "id": 1,
            "recorded_at": "2999-01-01T00:01:00Z",
            "relay_on": True,
            "reason": "temperature_above_cooling_threshold",
            "temperature_c": 18.7,
        }
    ]


def test_temperature_readings_validate_span_bounds(tmp_path: Path) -> None:
    db_path = tmp_path / "validation.db"

    with TestClient(create_app(_write_config(tmp_path, db_path))) as client:
        too_short = client.get("/api/temperature-readings?span_minutes=4")
        too_long = client.get("/api/temperature-readings?span_minutes=1441")

    assert too_short.status_code == 422
    assert too_long.status_code == 422


def test_relay_events_respects_limit(tmp_path: Path) -> None:
    db_path = tmp_path / "relay-events.db"
    config_path = _write_config(tmp_path, db_path)
    db.migrate(db_path)
    _insert_relay_event(
        db_path,
        recorded_at="2999-01-01 00:01:00",
        relay_on=True,
        reason="on",
        temperature_c=18.8,
    )
    _insert_relay_event(
        db_path,
        recorded_at="2999-01-01 00:02:00",
        relay_on=False,
        reason="off",
        temperature_c=17.9,
    )

    with TestClient(create_app(config_path)) as client:
        response = client.get("/api/relay-events?limit=1")

    assert response.status_code == 200
    assert response.json()["events"] == [
        {
            "id": 2,
            "recorded_at": "2999-01-01T00:02:00Z",
            "relay_on": False,
            "reason": "off",
            "temperature_c": 17.9,
        }
    ]


def test_cors_allows_configured_origin(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cors.db"
    monkeypatch.setenv("AXOCARE_CORS_ORIGINS", "http://frontend.test")

    with TestClient(create_app(_write_config(tmp_path, db_path))) as client:
        response = client.options(
            "/api/current",
            headers={
                "Origin": "http://frontend.test",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://frontend.test"


def test_openapi_schema_is_served_under_api_prefix(tmp_path: Path) -> None:
    db_path = tmp_path / "openapi.db"

    with TestClient(create_app(_write_config(tmp_path, db_path))) as client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json()["openapi"].startswith("3.")


def _write_config(tmp_path: Path, db_path: Path) -> Path:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[database]
path = "{db_path}"

[temperature]
target_c = 18.0
cooling_on_c = 18.6
cooling_off_c = 18.0

[control]
interval_seconds = 60
""".strip(),
        encoding="utf-8",
    )
    return config_path


def _insert_temperature(
    db_path: Path,
    *,
    recorded_at: str,
    temperature_c: float,
    relay_on: bool,
    sensor_id: str,
) -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO temperature_readings (
                recorded_at,
                temperature_c,
                relay_on,
                sensor_id,
                error
            )
            VALUES (?, ?, ?, ?, NULL)
            """,
            (recorded_at, temperature_c, int(relay_on), sensor_id),
        )
        conn.commit()


def _insert_relay_event(
    db_path: Path,
    *,
    recorded_at: str,
    relay_on: bool,
    reason: str,
    temperature_c: float,
) -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO relay_events (
                recorded_at,
                relay_on,
                reason,
                temperature_c
            )
            VALUES (?, ?, ?, ?)
            """,
            (recorded_at, int(relay_on), reason, temperature_c),
        )
        conn.commit()
