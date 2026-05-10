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

[pushover]
app_token = "app-token"
user_key = "user-key"
title = "Hot tank"
""".strip(),
        encoding="utf-8",
    )

    config = control.ControlConfig.from_toml(config_path)

    assert config.notification_threshold_c == 21.5
    assert config.pushover_app_token == "app-token"
    assert config.pushover_user_key == "user-key"
    assert config.pushover_title == "Hot tank"


def _config(notification_threshold_c: float | None) -> control.ControlConfig:
    return control.ControlConfig(
        db_path=":memory:",
        target_c=18.0,
        cooling_on_c=18.6,
        cooling_off_c=18.0,
        notification_threshold_c=notification_threshold_c,
        interval_seconds=60,
        relay_pin=26,
        relay_active_high=False,
        sensor_id=None,
        pushover_app_token="app-token",
        pushover_user_key="user-key",
        pushover_title="Axocare temperature alert",
    )
