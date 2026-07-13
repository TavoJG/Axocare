from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from axocare_ai.predict import predict_from_db
from axocare_ai.train import train_model
import db as axocare_db


def test_train_model_handles_null_ambient_history(tmp_path: Path) -> None:
    db_path = _seed_training_database(tmp_path)
    models_dir = tmp_path / "models"

    result = train_model(db_path, 10, output_dir=models_dir)

    assert result["model_name"] == "thermal_ridge"
    assert result["horizon_minutes"] == 10
    assert result["ambient_missing_rows"]["room_temperature"] > 0
    assert result["ambient_missing_rows"]["humidity"] > 0
    assert (models_dir / "thermal_ridge_h10.json").exists()


def test_predict_from_db_returns_live_prediction(tmp_path: Path) -> None:
    db_path = _seed_training_database(tmp_path)
    models_dir = tmp_path / "models"
    train_model(db_path, 15, output_dir=models_dir)

    prediction = predict_from_db(db_path, 15, models_dir=models_dir)

    assert prediction["available"] is True
    assert prediction["model_name"] == "thermal_ridge"
    assert prediction["horizon_minutes"] == 15
    assert prediction["predicted_temperature_c"] != prediction["current_temperature_c"]
    assert prediction["risk_level"] in {"low", "medium", "high"}


def _seed_training_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "axocare.db"
    axocare_db.migrate(db_path)
    start = datetime.now(timezone.utc) - timedelta(minutes=150)

    with axocare_db.connect(db_path) as conn:
        for minute in range(120):
            room_temperature = None if minute < 50 else 23.5 + ((minute % 7) * 0.09)
            humidity = None if minute < 50 else 46.0 + ((minute % 4) * 0.8)
            relay_on = 1 if minute % 20 >= 14 else 0
            trend_component = 0.006 * minute
            cooling_component = -0.14 if relay_on else 0.05
            water_temp = 18.1 + trend_component + cooling_component
            conn.execute(
                """
                INSERT INTO temperature_readings (
                    recorded_at,
                    temperature_c,
                    relay_on,
                    room_temperature,
                    aht20_humidity_percent,
                    bmp280_pressure_hpa
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _sqlite_utc(start + timedelta(minutes=minute)),
                    round(water_temp, 3),
                    relay_on,
                    room_temperature,
                    humidity,
                    1011.5 + ((minute % 3) * 0.4),
                ),
            )
        conn.commit()
    return db_path


def _sqlite_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
