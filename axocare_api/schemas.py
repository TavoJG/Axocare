"""Response schemas for the Axocare API."""

from __future__ import annotations

from pydantic import BaseModel

from axocare_api.settings import ApiSettings


class TemperatureReading(BaseModel):
    """One persisted temperature reading."""

    id: int
    recorded_at: str
    temperature_c: float | None
    relay_on: bool
    sensor_id: str | None
    error: str | None


class RelayEvent(BaseModel):
    """One persisted relay state transition."""

    id: int
    recorded_at: str
    relay_on: bool
    reason: str
    temperature_c: float | None


class HealthResponse(BaseModel):
    """Basic process health for lightweight monitoring."""

    status: str
    db_path: str


class CurrentReadingResponse(BaseModel):
    """Current dashboard status."""

    reading: TemperatureReading | None
    db_path: str


class TemperatureHistoryResponse(BaseModel):
    """Temperature readings for a requested time span."""

    span_minutes: int
    readings: list[TemperatureReading]


class RelayEventsResponse(BaseModel):
    """Recent relay events."""

    events: list[RelayEvent]


class DashboardResponse(BaseModel):
    """Single payload convenient for a frontend dashboard view."""

    db_path: str
    settings: ApiSettings
    current: TemperatureReading | None
    readings: list[TemperatureReading]
    relay_events: list[RelayEvent]
    span_minutes: int
