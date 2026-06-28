from __future__ import annotations

from pathlib import Path

import control


class FakeNotifier:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def notify_temperature_high(
        self,
        *,
        temperature_c: float,
        threshold_c: float,
        sensor_id: str | None,
    ) -> None:
        self.calls.append(
            {
                "temperature_c": temperature_c,
                "threshold_c": threshold_c,
                "sensor_id": sensor_id,
            }
        )


def test_high_temperature_notification_sends_once_until_temperature_recovers() -> None:
    config = _config(notification_threshold_c=20.0)
    notifier = FakeNotifier()
    state = control.TemperatureNotificationState()

    control.maybe_notify_temperature(
        control.SensorReading(20.1, "sensor-1"),
        config=config,
        notifier=notifier,
        notification_state=state,
    )
    control.maybe_notify_temperature(
        control.SensorReading(20.3, "sensor-1"),
        config=config,
        notifier=notifier,
        notification_state=state,
    )
    control.maybe_notify_temperature(
        control.SensorReading(20.0, "sensor-1"),
        config=config,
        notifier=notifier,
        notification_state=state,
    )
    control.maybe_notify_temperature(
        control.SensorReading(20.2, "sensor-1"),
        config=config,
        notifier=notifier,
        notification_state=state,
    )

    assert notifier.calls == [
        {
            "temperature_c": 20.1,
            "threshold_c": 20.0,
            "sensor_id": "sensor-1",
        },
        {
            "temperature_c": 20.2,
            "threshold_c": 20.0,
            "sensor_id": "sensor-1",
        },
    ]


def test_notification_is_disabled_without_threshold() -> None:
    config = _config(notification_threshold_c=None)
    notifier = FakeNotifier()

    control.maybe_notify_temperature(
        control.SensorReading(99.0, "sensor-1"),
        config=config,
        notifier=notifier,
        notification_state=control.TemperatureNotificationState(),
    )

    assert notifier.calls == []


def test_config_loads_notification_and_pushover_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[database]
path = "{tmp_path / "axocare.db"}"

[temperature]
notification_threshold_c = 21.5

[i2c_sensor]
enabled = true
aht20_address = 0x38
bmp280_address = "0x77"

[pushover]
app_token = "app-token"
user_key = "user-key"
title = "Hot tank"
""".strip(),
        encoding="utf-8",
    )

    config = control.ControlConfig.from_toml(config_path)

    assert config.notification_threshold_c == 21.5
    assert config.i2c_sensor_enabled is True
    assert config.aht20_address == 0x38
    assert config.bmp280_address == 0x77
    assert config.pushover_app_token == "app-token"
    assert config.pushover_user_key == "user-key"
    assert config.pushover_title == "Hot tank"


def test_control_once_records_ambient_telemetry(tmp_path: Path) -> None:
    db_path = tmp_path / "ambient.db"
    control.db.migrate(db_path)

    relay_on = control.control_once(
        None,
        current_relay_on=False,
        sensor=_FakeSensor(18.9, "tank-probe"),
        ambient_sensor=_FakeAmbientSensor(),
        config=_config(notification_threshold_c=None, db_path=str(db_path)),
        dry_run_temperature=None,
        db_path=db_path,
    )

    assert relay_on is True
    row = control.db.latest_temperature(db_path=db_path)
    assert row is not None
    assert row["temperature_c"] == 18.9
    assert row["relay_on"] == 1
    assert row["sensor_id"] == "tank-probe"
    assert row["room_temperature"] == 24.1
    assert row["aht20_humidity_percent"] == 56.2
    assert row["bmp280_temperature_c"] == 23.8
    assert row["bmp280_pressure_hpa"] == 1009.4
    assert row["ambient_error"] is None


class _FakeSensor:
    def __init__(self, temperature_c: float, sensor_id: str) -> None:
        self._temperature_c = temperature_c
        self.id = sensor_id

    def get_temperature(self) -> float:
        return self._temperature_c


class _FakeAmbientSensor:
    def read(self) -> control.AmbientReading:
        return control.AmbientReading(
            room_temperature=24.1,
            aht20_humidity_percent=56.2,
            bmp280_temperature_c=23.8,
            bmp280_pressure_hpa=1009.4,
        )


def _config(
    notification_threshold_c: float | None,
    *,
    db_path: str = ":memory:",
) -> control.ControlConfig:
    return control.ControlConfig(
        db_path=db_path,
        target_c=18.0,
        cooling_on_c=18.6,
        cooling_off_c=18.0,
        notification_threshold_c=notification_threshold_c,
        interval_seconds=60,
        relay_pin=26,
        relay_active_high=False,
        sensor_id=None,
        i2c_sensor_enabled=False,
        aht20_address=0x38,
        bmp280_address=0x77,
        pushover_app_token="app-token",
        pushover_user_key="user-key",
        pushover_title="Axocare temperature alert",
    )
