"""HTTP routes for the Axocare API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

import db
from axocare_api.schemas import (
    CurrentReadingResponse,
    DashboardResponse,
    HealthResponse,
    RelayEventsResponse,
    TemperatureHistoryResponse,
)
from axocare_api.serializers import relay_event, temperature_reading
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
        },
    }


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health(api_settings: ApiSettings = Depends(settings)) -> HealthResponse:
    return HealthResponse(status="ok", db_path=api_settings.db_path)


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
