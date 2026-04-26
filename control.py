"""Aquarium cooling controller main logic."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import db

try:
    import RPi.GPIO as GPIO
except ImportError:  # Development machines usually do not have RPi.GPIO.
    GPIO = None

DEFAULT_CONFIG_PATH = "config.toml"


@dataclass(frozen=True)
class SensorReading:
    """Temperature reading returned by the DS18B20 sensor layer."""

    temperature_c: float | None
    sensor_id: str | None
    error: str | None = None


@dataclass(frozen=True)
class ControlConfig:
    """Runtime controller settings loaded from the TOML configuration file."""

    db_path: str
    target_c: float
    cooling_on_c: float
    cooling_off_c: float
    interval_seconds: int
    relay_pin: int
    relay_active_high: bool
    sensor_id: str | None

    @classmethod
    def from_toml(cls, config_path: str | Path) -> "ControlConfig":
        """Build typed controller configuration from a TOML file."""
        path = Path(config_path)
        values = tomllib.loads(path.read_text(encoding="utf-8"))
        database = values.get("database", {})
        temperature = values.get("temperature", {})
        control = values.get("control", {})
        relay = values.get("relay", {})
        sensor = values.get("sensor", {})

        return cls(
            db_path=str(database.get("path", db.DEFAULT_DB_PATH)),
            target_c=float(temperature.get("target_c", 25.0)),
            cooling_on_c=float(temperature.get("cooling_on_c", 25.5)),
            cooling_off_c=float(temperature.get("cooling_off_c", 25.0)),
            interval_seconds=int(control.get("interval_seconds", 60)),
            relay_pin=int(relay.get("pin", 25)),
            relay_active_high=bool(relay.get("active_high", True)),
            sensor_id=sensor.get("id") or None,
        )


class Relay:
    """GPIO-backed relay output for switching the cooling device."""

    def __init__(self, pin: int, active_high: bool) -> None:
        """Initialize the relay pin and leave the relay in the off state."""
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed; run this on a Raspberry Pi.")

        self.pin = pin
        self.active_high = active_high
        self.is_on = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT, initial=self._gpio_level(False))

    def set(self, enabled: bool) -> None:
        """Turn the relay on or off."""
        GPIO.output(self.pin, self._gpio_level(enabled))
        self.is_on = enabled

    def cleanup(self) -> None:
        """Turn the relay off and release the GPIO pin."""
        self.set(False)
        GPIO.cleanup(self.pin)

    def _gpio_level(self, enabled: bool) -> int:
        """Convert logical relay state to the physical GPIO output level."""
        if self.active_high:
            return GPIO.HIGH if enabled else GPIO.LOW
        return GPIO.LOW if enabled else GPIO.HIGH


def create_sensor(sensor_id: str | None = None):
    """Create a DS18B20 sensor instance using w1thermsensor."""
    try:
        from w1thermsensor import W1ThermSensor
    except Exception as exc:
        raise RuntimeError(
            "w1thermsensor is not installed; install it on the Raspberry Pi first."
        ) from exc

    if sensor_id:
        return W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, sensor_id)
    return W1ThermSensor()


def read_temperature(sensor, dry_run_temperature: float | None = None) -> SensorReading:
    """Read Celsius temperature from the sensor or return a simulated reading."""
    if dry_run_temperature is not None:
        return SensorReading(dry_run_temperature, "dry-run")

    try:
        return SensorReading(sensor.get_temperature(), getattr(sensor, "id", None))
    except Exception as exc:
        sensor_id = getattr(sensor, "id", None)
        return SensorReading(None, sensor_id, f"sensor_read_error: {exc}")


def next_relay_state(
    current_on: bool,
    temperature_c: float | None,
    config: ControlConfig,
) -> tuple[bool, str | None]:
    """Decide the next relay state from temperature and configured thresholds."""
    if temperature_c is None:
        return False, "sensor_error" if current_on else None

    if temperature_c >= config.cooling_on_c and not current_on:
        return True, "temperature_above_cooling_threshold"

    if temperature_c <= config.cooling_off_c and current_on:
        return False, "temperature_at_or_below_target"

    return current_on, None


def control_once(
    relay: Relay | None,
    *,
    current_relay_on: bool,
    sensor,
    config: ControlConfig,
    dry_run_temperature: float | None,
    db_path: str | Path,
) -> bool:
    """Run one control cycle and persist the reading plus any relay transition."""
    reading = read_temperature(sensor, dry_run_temperature)
    desired_relay_on, reason = next_relay_state(
        current_relay_on,
        reading.temperature_c,
        config,
    )

    if relay is not None and desired_relay_on != current_relay_on:
        relay.set(desired_relay_on)

    db.record_temperature(
        reading.temperature_c,
        desired_relay_on,
        sensor_id=reading.sensor_id,
        error=reading.error,
        db_path=db_path,
    )

    if desired_relay_on != current_relay_on:
        db.record_relay_event(
            desired_relay_on,
            reason or "state_changed",
            temperature_c=reading.temperature_c,
            db_path=db_path,
        )

    logging.info(
        "temperature=%s relay_on=%s error=%s",
        reading.temperature_c,
        desired_relay_on,
        reading.error,
    )
    return desired_relay_on


def run(
    *,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    once: bool = False,
    dry_run: bool = False,
    dry_run_temperature: float | None = None,
) -> None:
    """Run the controller loop until interrupted or for one iteration."""
    config = ControlConfig.from_toml(config_path)
    db.migrate(config.db_path)
    relay = (
        None
        if dry_run
        else Relay(pin=config.relay_pin, active_high=config.relay_active_high)
    )
    sensor = (
        None if dry_run_temperature is not None else create_sensor(config.sensor_id)
    )
    relay_on = False
    stopping = False

    def stop(_signum, _frame) -> None:
        """Request a graceful shutdown from a process signal."""
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while not stopping:
            relay_on = control_once(
                relay,
                current_relay_on=relay_on,
                sensor=sensor,
                config=config,
                dry_run_temperature=dry_run_temperature,
                db_path=config.db_path,
            )
            if once:
                break
            time.sleep(config.interval_seconds)
    finally:
        if relay is not None:
            relay.cleanup()


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the controller process."""
    parser = argparse.ArgumentParser(description="Axocare aquarium cooling controller")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="TOML configuration file path",
    )
    parser.add_argument("--once", action="store_true", help="Run one loop and exit")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not use GPIO; useful for development.",
    )
    parser.add_argument(
        "--dry-run-temperature",
        type=float,
        default=None,
        help="Use this temperature instead of reading a real w1 sensor.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entrypoint and return a process exit code."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = parse_args(argv or sys.argv[1:])
    try:
        run(
            config_path=args.config,
            once=args.once,
            dry_run=args.dry_run,
            dry_run_temperature=args.dry_run_temperature,
        )
    except Exception:
        logging.exception("control loop failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
