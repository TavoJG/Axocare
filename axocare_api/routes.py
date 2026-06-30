"""HTTP routes for the Axocare API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

import db
from axocare_api.schemas import (
    ControlHealth,
    CurrentReadingResponse,
    DashboardResponse,
    HealthResponse,
    RelayEventsResponse,
    TemperatureHistoryResponse,
)
from axocare_api.serializers import relay_event, temperature_reading
from axocare_api.serializers import recorded_at as serialized_recorded_at
from axocare_api.settings import DEFAULT_HISTORY_MINUTES, DEFAULT_LIMIT, ApiSettings

router = APIRouter(
    prefix="/api",
)

def settings(request: Request) -> ApiSettings:
    """Return settings loaded during application startup."""
    return request.app.state.settings


@router.get("/", tags=["meta"])
def root() -> dict[str, Any]:
    return {
        "name": "Axocare API",
        "endpoints": {
            "health": "/health",
            "dashboard": "/api/dashboard",
            "current": "/api/current",
            "temperature_readings": "/api/temperature-readings",
            "relay_events": "/api/relay-events",
            "camera_stream": "/api/camera/stream",
            "camera_stream_source": "/camera/stream",
        },
    }


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(api_settings: ApiSettings = Depends(settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        db_path=api_settings.db_path,
        control=_control_health(api_settings),
    )


def _control_health(api_settings: ApiSettings) -> ControlHealth:
    """Infer whether the controller is still producing healthy readings."""
    row = db.latest_temperature(db_path=api_settings.db_path)
    max_age_seconds = max(api_settings.interval_seconds * 2, 1)

    if row is None:
        return ControlHealth(
            status="unknown",
            latest_reading_at=None,
            age_seconds=None,
            max_age_seconds=max_age_seconds,
            temperature_c=None,
            relay_on=None,
            last_error=None,
        )

    latest_reading_at = serialized_recorded_at(row["recorded_at"])
    age_seconds = _reading_age_seconds(row["recorded_at"])
    last_error = row["error"]
    status = "ok"
    if last_error:
        status = "error"
    elif age_seconds is None or age_seconds > max_age_seconds:
        status = "stale"

    return ControlHealth(
        status=status,
        latest_reading_at=latest_reading_at,
        age_seconds=age_seconds,
        max_age_seconds=max_age_seconds,
        temperature_c=row["temperature_c"],
        relay_on=bool(row["relay_on"]),
        last_error=last_error,
    )


def _reading_age_seconds(recorded_at: str) -> int | None:
    """Return how many seconds ago a SQLite UTC timestamp was written."""
    try:
        if recorded_at.endswith("Z"):
            recorded_at_dt = datetime.fromisoformat(
                recorded_at.removesuffix("Z")
            ).replace(tzinfo=timezone.utc)
        else:
            recorded_at_dt = datetime.fromisoformat(recorded_at.replace(" ", "T"))
            if recorded_at_dt.tzinfo is None:
                recorded_at_dt = recorded_at_dt.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - recorded_at_dt
    except ValueError:
        return None

    return max(0, int(age.total_seconds()))


@router.get(
    "/current",
    response_model=CurrentReadingResponse,
    tags=["dashboard"],
)
def current_reading(
    api_settings: ApiSettings = Depends(settings),
) -> CurrentReadingResponse:
    row = db.latest_temperature(db_path=api_settings.db_path)
    return CurrentReadingResponse(
        reading=temperature_reading(row) if row is not None else None,
        db_path=api_settings.db_path,
    )


@router.get(
    "/temperature-readings",
    response_model=TemperatureHistoryResponse,
    tags=["dashboard"],
)
def temperature_readings(
    span_minutes: int = Query(
        DEFAULT_HISTORY_MINUTES,
        ge=5,
        le=24 * 60,
        description="Time span to return, in minutes.",
    ),
    api_settings: ApiSettings = Depends(settings),
) -> TemperatureHistoryResponse:
    rows = db.temperatures_since(span_minutes, db_path=api_settings.db_path)
    return TemperatureHistoryResponse(
        span_minutes=span_minutes,
        readings=[temperature_reading(row) for row in rows],
    )


@router.get(
    "/relay-events",
    response_model=RelayEventsResponse,
    tags=["dashboard"],
)
def relay_events(
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=500,
        description="Maximum number of relay events to return.",
    ),
    api_settings: ApiSettings = Depends(settings),
) -> RelayEventsResponse:
    rows = db.latest_relay_events(limit, db_path=api_settings.db_path)
    return RelayEventsResponse(events=[relay_event(row) for row in rows])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    tags=["dashboard"],
)
def dashboard(
    span_minutes: int = Query(
        DEFAULT_HISTORY_MINUTES,
        ge=5,
        le=24 * 60,
        description="Time span to return, in minutes.",
    ),
    event_limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=500,
        description="Maximum number of relay events to return.",
    ),
    api_settings: ApiSettings = Depends(settings),
) -> DashboardResponse:
    current = db.latest_temperature(db_path=api_settings.db_path)
    readings = db.temperatures_since(span_minutes, db_path=api_settings.db_path)
    events = db.latest_relay_events(event_limit, db_path=api_settings.db_path)

    return DashboardResponse(
        db_path=api_settings.db_path,
        settings=api_settings,
        current=temperature_reading(current) if current is not None else None,
        readings=[temperature_reading(row) for row in readings],
        relay_events=[relay_event(row) for row in events],
        span_minutes=span_minutes,
    )


@router.get("/camera/stream", tags=["camera"])
def camera_stream_redirect(
    api_settings: ApiSettings = Depends(settings),
) -> RedirectResponse:
    if not api_settings.camera_enabled:
        raise HTTPException(status_code=404, detail="Camera streaming is disabled")

    if not api_settings.camera_stream_url:
        raise HTTPException(
            status_code=503,
            detail="Camera stream URL is not configured",
        )

    return RedirectResponse(url=api_settings.camera_stream_url, status_code=307)
