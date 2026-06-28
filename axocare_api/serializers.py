"""SQLite row serializers for API responses."""

from __future__ import annotations

from axocare_api.schemas import RelayEvent, TemperatureReading


def temperature_reading(row) -> TemperatureReading:
    """Convert a SQLite row to a JSON-safe temperature reading."""
    return TemperatureReading(
        id=int(row["id"]),
        recorded_at=recorded_at(row["recorded_at"]),
        temperature_c=row["temperature_c"],
        relay_on=bool(row["relay_on"]),
        sensor_id=row["sensor_id"],
        error=row["error"],
        room_temperature=row["room_temperature"],
        aht20_humidity_percent=row["aht20_humidity_percent"],
        bmp280_temperature_c=row["bmp280_temperature_c"],
        bmp280_pressure_hpa=row["bmp280_pressure_hpa"],
        ambient_error=row["ambient_error"],
    )


def relay_event(row) -> RelayEvent:
    """Convert a SQLite row to a JSON-safe relay event."""
    return RelayEvent(
        id=int(row["id"]),
        recorded_at=recorded_at(row["recorded_at"]),
        relay_on=bool(row["relay_on"]),
        reason=row["reason"],
        temperature_c=row["temperature_c"],
    )


def recorded_at(value: str) -> str:
    """Return SQLite UTC timestamps in ISO-like form for browser clients."""
    if "T" in value:
        return value
    return f"{value.replace(' ', 'T')}Z"
