"""Aquarium cooling controller main logic."""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib import error, parse, request

import db

try:
    import RPi.GPIO as GPIO
except ImportError:  # Development machines usually do not have RPi.GPIO.
    GPIO = None

DEFAULT_CONFIG_PATH = "config.toml"
WAVESHARE_RPI_RELAY_CH1_BCM_PIN = 26
WAVESHARE_RPI_RELAY_CH2_BCM_PIN = 20
WAVESHARE_RPI_RELAY_DEFAULT_BCM_PINS = (
    WAVESHARE_RPI_RELAY_CH1_BCM_PIN,
    WAVESHARE_RPI_RELAY_CH2_BCM_PIN,
)
WAVESHARE_RPI_RELAY_ACTIVE_HIGH = False
DEFAULT_AHT20_ADDRESS = 0x38
DEFAULT_BMP280_ADDRESS = 0x77


@dataclass(frozen=True)
class SensorReading:
    """Temperature reading returned by the DS18B20 sensor layer."""

    temperature_c: float | None
    sensor_id: str | None
    error: str | None = None


@dataclass(frozen=True)
class AmbientReading:
    """Ambient telemetry returned by the optional AHT20 + BMP280 I2C module."""

    aht20_temperature_c: float | None = None
    aht20_humidity_percent: float | None = None
    bmp280_temperature_c: float | None = None
    bmp280_pressure_hpa: float | None = None
    error: str | None = None


@dataclass(frozen=True)
class ControlConfig:
    """Runtime controller settings loaded from the TOML configuration file."""

    db_path: str
    target_c: float
    cooling_on_c: float
    cooling_off_c: float
    notification_threshold_c: float | None
    interval_seconds: int
    relay_pin: int
    relay_active_high: bool
    sensor_id: str | None
    i2c_sensor_enabled: bool
    aht20_address: int
    bmp280_address: int
    pushover_app_token: str | None
    pushover_user_key: str | None
    pushover_title: str
    relay_pins: tuple[int, ...] = WAVESHARE_RPI_RELAY_DEFAULT_BCM_PINS

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
        i2c_sensor = values.get("i2c_sensor", {})
        pushover = values.get("pushover", {})

        return cls(
            db_path=str(database.get("path", db.DEFAULT_DB_PATH)),
            target_c=float(temperature.get("target_c", 25.0)),
            cooling_on_c=float(temperature.get("cooling_on_c", 25.5)),
            cooling_off_c=float(temperature.get("cooling_off_c", 25.0)),
            notification_threshold_c=_optional_float(
                temperature.get("notification_threshold_c")
            ),
            interval_seconds=int(control.get("interval_seconds", 60)),
            relay_pin=int(relay.get("pin", WAVESHARE_RPI_RELAY_CH1_BCM_PIN)),
            relay_pins=_relay_pins_from_config(relay),
            relay_active_high=bool(
                relay.get("active_high", WAVESHARE_RPI_RELAY_ACTIVE_HIGH)
            ),
            sensor_id=sensor.get("id") or None,
            i2c_sensor_enabled=bool(i2c_sensor.get("enabled", False)),
            aht20_address=_parse_i2c_address(
                i2c_sensor.get("aht20_address", DEFAULT_AHT20_ADDRESS)
            ),
            bmp280_address=_parse_i2c_address(
                i2c_sensor.get("bmp280_address", DEFAULT_BMP280_ADDRESS)
            ),
            pushover_app_token=_optional_str(
                pushover.get("app_token") or os.getenv("PUSHOVER_APP_TOKEN")
            ),
            pushover_user_key=_optional_str(
                pushover.get("user_key") or os.getenv("PUSHOVER_USER_KEY")
            ),
            pushover_title=str(pushover.get("title") or "Axocare temperature alert"),
        )


@dataclass
class TemperatureNotificationState:
    """Tracks whether the high-temperature notification is already active."""

    active: bool = False


class TemperatureNotifier(Protocol):
    """Notifier interface used by the controller loop."""

    def notify_temperature_high(
        self,
        *,
        temperature_c: float,
        threshold_c: float,
        sensor_id: str | None,
    ) -> None:
        """Send a high-temperature notification."""


class PushoverNotifier:
    """Small Pushover client for controller alerts."""

    API_URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, *, app_token: str, user_key: str, title: str) -> None:
        self.app_token = app_token
        self.user_key = user_key
        self.title = title

    def notify_temperature_high(
        self,
        *,
        temperature_c: float,
        threshold_c: float,
        sensor_id: str | None,
    ) -> None:
        message = (
            f"Temperature is {temperature_c:.2f} C, above the "
            f"{threshold_c:.2f} C notification threshold."
        )
        if sensor_id:
            message = f"{message} Sensor: {sensor_id}."

        payload = parse.urlencode(
            {
                "token": self.app_token,
                "user": self.user_key,
                "title": self.title,
                "message": message,
            }
        ).encode("utf-8")
        pushover_request = request.Request(
            self.API_URL,
            data=payload,
            method="POST",
        )

        try:
            with request.urlopen(pushover_request, timeout=10) as response:
                response.read()
        except error.URLError as exc:
            raise RuntimeError(f"Pushover notification failed: {exc}") from exc


class Relay:
    """GPIO-backed relay outputs for switching the cooling device."""

    def __init__(self, pins: tuple[int, ...] | list[int], active_high: bool) -> None:
        """Initialize relay pins and leave the relays in the off state."""
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed; run this on a Raspberry Pi.")

        self.pins = tuple(pins)
        self.active_high = active_high
        self.is_on = False

        GPIO.setmode(GPIO.BCM)
        for pin in self.pins:
            GPIO.cleanup(pin)
            GPIO.setup(pin, GPIO.OUT, initial=self._gpio_level(False))

    def set(self, enabled: bool) -> None:
        """Turn the relays on or off."""
        for pin in self.pins:
            GPIO.output(pin, self._gpio_level(enabled))
        self.is_on = enabled

    def cleanup(self) -> None:
        """Turn the relays off and release the GPIO pins."""
        self.set(False)
        for pin in self.pins:
            GPIO.cleanup(pin)

    def _gpio_level(self, enabled: bool) -> int:
        """Convert logical relay state to the physical GPIO output level."""
        if self.active_high:
            return GPIO.HIGH if enabled else GPIO.LOW
        return GPIO.LOW if enabled else GPIO.HIGH


class CombinedI2CSensor:
    """Read the optional AHT20 and BMP280 sensors on a shared I2C bus."""

    def __init__(self, *, aht20_address: int, bmp280_address: int) -> None:
        self._aht20 = None
        self._bmp280 = None
        self._init_error: str | None = None

        try:
            import adafruit_ahtx0
            import adafruit_bmp280
            import board
            import busio
        except Exception as exc:
            self._init_error = f"i2c_init_error: {exc}"
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self._aht20 = adafruit_ahtx0.AHTx0(i2c, address=aht20_address)
            self._bmp280 = adafruit_bmp280.Adafruit_BMP280_I2C(
                i2c,
                address=bmp280_address,
            )
        except Exception as exc:
            self._init_error = f"i2c_init_error: {exc}"

    def read(self) -> AmbientReading:
        """Return best-effort telemetry, preserving partial readings when possible."""
        if self._init_error:
            return AmbientReading(error=self._init_error)

        aht20_temperature_c = None
        aht20_humidity_percent = None
        bmp280_temperature_c = None
        bmp280_pressure_hpa = None
        errors: list[str] = []

        if self._aht20 is not None:
            try:
                aht20_temperature_c = float(self._aht20.temperature)
                aht20_humidity_percent = float(self._aht20.relative_humidity)
            except Exception as exc:
                errors.append(f"aht20_read_error: {exc}")

        if self._bmp280 is not None:
            try:
                bmp280_temperature_c = float(self._bmp280.temperature)
                bmp280_pressure_hpa = float(self._bmp280.pressure)
            except Exception as exc:
                errors.append(f"bmp280_read_error: {exc}")

        return AmbientReading(
            aht20_temperature_c=aht20_temperature_c,
            aht20_humidity_percent=aht20_humidity_percent,
            bmp280_temperature_c=bmp280_temperature_c,
            bmp280_pressure_hpa=bmp280_pressure_hpa,
            error="; ".join(errors) or None,
        )


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


def create_i2c_sensor(config: ControlConfig) -> CombinedI2CSensor | None:
    """Create the optional ambient I2C sensor bundle when enabled."""
    if not config.i2c_sensor_enabled:
        return None
    return CombinedI2CSensor(
        aht20_address=config.aht20_address,
        bmp280_address=config.bmp280_address,
    )


def read_ambient(sensor: CombinedI2CSensor | None) -> AmbientReading:
    """Read optional ambient telemetry or return an empty reading when disabled."""
    if sensor is None:
        return AmbientReading()
    return sensor.read()


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


def create_notifier(config: ControlConfig) -> TemperatureNotifier | None:
    """Create a configured notification client, if alerting is enabled."""
    if config.notification_threshold_c is None:
        return None

    if not config.pushover_app_token or not config.pushover_user_key:
        logging.warning(
            "temperature notification threshold is configured, but Pushover "
            "credentials are missing"
        )
        return None

    return PushoverNotifier(
        app_token=config.pushover_app_token,
        user_key=config.pushover_user_key,
        title=config.pushover_title,
    )


def maybe_notify_temperature(
    reading: SensorReading,
    *,
    config: ControlConfig,
    notifier: TemperatureNotifier | None,
    notification_state: TemperatureNotificationState,
) -> None:
    """Send one notification per high-temperature excursion."""
    threshold_c = config.notification_threshold_c
    temperature_c = reading.temperature_c

    if threshold_c is None or notifier is None or temperature_c is None:
        return

    if temperature_c <= threshold_c:
        notification_state.active = False
        return

    if notification_state.active:
        return

    try:
        notifier.notify_temperature_high(
            temperature_c=temperature_c,
            threshold_c=threshold_c,
            sensor_id=reading.sensor_id,
        )
    except Exception:
        logging.exception("temperature notification failed")
        return

    notification_state.active = True


def control_once(
    relay: Relay | None,
    *,
    current_relay_on: bool,
    sensor,
    ambient_sensor: CombinedI2CSensor | None,
    config: ControlConfig,
    dry_run_temperature: float | None,
    db_path: str | Path,
    notifier: TemperatureNotifier | None = None,
    notification_state: TemperatureNotificationState | None = None,
) -> bool:
    """Run one control cycle and persist the reading plus any relay transition."""
    reading = read_temperature(sensor, dry_run_temperature)
    ambient = read_ambient(ambient_sensor)
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
        aht20_temperature_c=ambient.aht20_temperature_c,
        aht20_humidity_percent=ambient.aht20_humidity_percent,
        bmp280_temperature_c=ambient.bmp280_temperature_c,
        bmp280_pressure_hpa=ambient.bmp280_pressure_hpa,
        ambient_error=ambient.error,
        db_path=db_path,
    )

    if desired_relay_on != current_relay_on:
        db.record_relay_event(
            desired_relay_on,
            reason or "state_changed",
            temperature_c=reading.temperature_c,
            db_path=db_path,
        )

    if notification_state is not None:
        maybe_notify_temperature(
            reading,
            config=config,
            notifier=notifier,
            notification_state=notification_state,
        )

    logging.info(
        "temperature=%s relay_on=%s aht20_temp=%s humidity=%s bmp280_temp=%s pressure=%s error=%s ambient_error=%s",
        reading.temperature_c,
        desired_relay_on,
        ambient.aht20_temperature_c,
        ambient.aht20_humidity_percent,
        ambient.bmp280_temperature_c,
        ambient.bmp280_pressure_hpa,
        reading.error,
        ambient.error,
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
    notifier = create_notifier(config)
    notification_state = TemperatureNotificationState()
    relay = (
        None
        if dry_run
        else Relay(pins=config.relay_pins, active_high=config.relay_active_high)
    )
    sensor = (
        None if dry_run_temperature is not None else create_sensor(config.sensor_id)
    )
    ambient_sensor = None if dry_run else create_i2c_sensor(config)
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
                ambient_sensor=ambient_sensor,
                config=config,
                dry_run_temperature=dry_run_temperature,
                db_path=config.db_path,
                notifier=notifier,
                notification_state=notification_state,
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


def _optional_float(value) -> float | None:
    """Return a float for configured values while treating blanks as disabled."""
    if value is None or value == "":
        return None
    return float(value)


def _optional_str(value) -> str | None:
    """Return a stripped string or None for blank secret/config values."""
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _parse_i2c_address(value) -> int:
    """Parse an I2C address from TOML as either an int or a hex string."""
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _relay_pins_from_config(relay: dict) -> tuple[int, ...]:
    """Return configured relay pins, defaulting to Waveshare CH1 and CH2."""
    if "pins" in relay:
        return tuple(int(pin) for pin in relay["pins"])
    if "pin" in relay:
        return _unique_pins((int(relay["pin"]), WAVESHARE_RPI_RELAY_CH2_BCM_PIN))
    return WAVESHARE_RPI_RELAY_DEFAULT_BCM_PINS


def _unique_pins(pins: tuple[int, ...]) -> tuple[int, ...]:
    """Keep relay pin order while removing duplicates."""
    unique: list[int] = []
    for pin in pins:
        if pin not in unique:
            unique.append(pin)
    return tuple(unique)


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
