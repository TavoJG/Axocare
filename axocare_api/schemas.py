"""Response schemas for the Axocare API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from axocare_api.settings import ApiSettings


class TemperatureReading(BaseModel):
    """One persisted temperature reading."""

    id: int
    recorded_at: str
    temperature_c: float | None
    relay_on: bool
    sensor_id: str | None
    error: str | None
    room_temperature: float | None
    aht20_humidity_percent: float | None
    bmp280_temperature_c: float | None
    bmp280_pressure_hpa: float | None
    ambient_error: str | None


class RelayEvent(BaseModel):
    """One persisted relay state transition."""

    id: int
    recorded_at: str
    relay_on: bool
    reason: str
    temperature_c: float | None


class ControlHealth(BaseModel):
    """Controller loop health inferred from persisted readings."""

    status: str
    latest_reading_at: str | None
    age_seconds: int | None
    max_age_seconds: int
    temperature_c: float | None
    relay_on: bool | None
    last_error: str | None


class HealthResponse(BaseModel):
    """Basic process health for lightweight monitoring."""

    status: str
    db_path: str
    control: ControlHealth


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


class AgentChatMessage(BaseModel):
    """One prior user or assistant message supplied by the dashboard."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class AgentChatRequest(BaseModel):
    """Browser-safe input for one grounded aquarium-agent response."""

    question: str = Field(min_length=1, max_length=4_000)
    conversation_id: str | None = Field(default=None, min_length=1, max_length=255)
    history: list[AgentChatMessage] = Field(default_factory=list, max_length=12)


class AgentChatResponse(BaseModel):
    """The agent's final natural-language answer."""

    conversation_id: str
    answer: str
