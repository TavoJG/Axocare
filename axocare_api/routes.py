"""HTTP routes for the Axocare API."""

from __future__ import annotations

from importlib import import_module
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse

import db
from axocare_agent.memory import build_summary, summary_message
from axocare_api.schemas import (
    AgentChatRequest,
    AgentChatResponse,
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

AGENT_UNAVAILABLE_MESSAGE = (
    "The aquarium agent is currently unavailable. Check its server configuration."
)
AGENT_RECENT_MESSAGE_LIMIT = 8


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
            "agent_chat": "/api/agent/chat",
            "agent_chat_stream": "/api/agent/chat/stream",
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


@router.post(
    "/agent/chat",
    response_model=AgentChatResponse,
    tags=["agent"],
)
async def agent_chat(
    payload: AgentChatRequest,
    request: Request,
    api_settings: ApiSettings = Depends(settings),
) -> AgentChatResponse:
    """Answer a dashboard question through the read-only MCP-grounded agent."""
    conversation_id = _prepare_agent_conversation(
        payload.conversation_id,
        payload.history,
        db_path=api_settings.db_path,
    )
    history = _agent_prompt_history(conversation_id, db_path=api_settings.db_path)
    try:
        answer = await _answer_agent(
            question=payload.question,
            history=history,
            config_path=request.app.state.config_path,
            db_path=api_settings.db_path,
            system_context=_agent_system_context(api_settings),
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail=AGENT_UNAVAILABLE_MESSAGE,
        ) from exc

    db.append_agent_messages(
        conversation_id,
        [("user", payload.question), ("assistant", answer)],
        db_path=api_settings.db_path,
    )
    return AgentChatResponse(conversation_id=conversation_id, answer=answer)


async def _answer_agent(
    *,
    question: str,
    history: list[dict[str, str]],
    config_path: str,
    db_path: str,
    system_context: str | None = None,
) -> str:
    """Create per-request provider and MCP sessions without exposing credentials."""
    AquariumAgent, AgentConfig, AxocareMcpClient, OpenAICompatibleProvider = _load_agent_runtime()

    config = AgentConfig.from_toml(config_path, db_path=db_path)

    provider = OpenAICompatibleProvider(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
    )
    async with AxocareMcpClient(
        config.db_path,
        startup_timeout_seconds=config.timeout_seconds,
    ) as mcp_client:
        agent = AquariumAgent(
            provider,
            mcp_client,
            max_tool_rounds=config.max_tool_rounds,
        )
        return await agent.answer(question, history, system_context=system_context)


@router.post(
    "/agent/chat/stream",
    tags=["agent"],
)
async def agent_chat_stream(
    payload: AgentChatRequest,
    request: Request,
    api_settings: ApiSettings = Depends(settings),
) -> StreamingResponse:
    """Stream safe agent lifecycle events as Server-Sent Events."""
    conversation_id = _prepare_agent_conversation(
        payload.conversation_id,
        payload.history,
        db_path=api_settings.db_path,
    )
    return StreamingResponse(
        _agent_sse_events(
            conversation_id=conversation_id,
            question=payload.question,
            history=_agent_prompt_history(conversation_id, db_path=api_settings.db_path),
            config_path=request.app.state.config_path,
            db_path=api_settings.db_path,
            system_context=_agent_system_context(api_settings),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _agent_sse_events(
    *,
    conversation_id: str,
    question: str,
    history: list[dict[str, str]],
    config_path: str,
    db_path: str,
    system_context: str | None = None,
) -> AsyncIterator[str]:
    """Yield browser-safe agent progress and completion events."""
    yield _sse_event("status", {"stage": "processing", "conversation_id": conversation_id})
    try:
        answer = await _answer_agent(
            question=question,
            history=history,
            config_path=config_path,
            db_path=db_path,
            system_context=system_context,
        )
    except (RuntimeError, ValueError):
        yield _sse_event(
            "error",
            {"message": AGENT_UNAVAILABLE_MESSAGE},
        )
        return

    db.append_agent_messages(
        conversation_id,
        [("user", question), ("assistant", answer)],
        db_path=db_path,
    )
    yield _sse_event("answer", {"answer": answer, "conversation_id": conversation_id})
    yield _sse_event("done", {})


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    """Encode one SSE event without exposing internal provider or MCP details."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _agent_system_context(api_settings: ApiSettings) -> str:
    """Provide stable runtime targets so the agent can answer config questions."""
    notification_threshold = (
        f"{api_settings.notification_threshold_c:.1f} C"
        if api_settings.notification_threshold_c is not None
        else "not configured"
    )
    return "\n".join(
        [
            f"Configured target water temperature: {api_settings.target_c:.1f} C.",
            f"Cooling turns on at: {api_settings.cooling_on_c:.1f} C.",
            f"Cooling turns off at: {api_settings.cooling_off_c:.1f} C.",
            f"Notification threshold: {notification_threshold}.",
        ]
    )


def _prepare_agent_conversation(
    conversation_id: str | None,
    history: list[Any],
    *,
    db_path: str,
) -> str:
    """Resolve or create a persisted agent conversation for one chat request."""
    if conversation_id is not None:
        if not db.agent_conversation_exists(conversation_id, db_path=db_path):
            raise HTTPException(status_code=404, detail="Agent conversation not found.")
        return conversation_id

    created_conversation_id = db.create_agent_conversation(db_path=db_path)
    bootstrap_messages = [
        (message.role, message.content) if hasattr(message, "role") else (message["role"], message["content"])
        for message in history
    ]
    db.append_agent_messages(created_conversation_id, bootstrap_messages, db_path=db_path)
    return created_conversation_id


def _agent_prompt_history(
    conversation_id: str,
    *,
    db_path: str,
    recent_limit: int = AGENT_RECENT_MESSAGE_LIMIT,
) -> list[dict[str, str]]:
    """Load summary memory plus recent raw messages for the agent prompt."""
    summary_row = db.agent_summary(conversation_id, db_path=db_path)
    summary_text = str(summary_row["summary"]) if summary_row is not None else None
    summarized_count = int(summary_row["summarized_message_count"]) if summary_row is not None else 0
    pending_rows = db.agent_messages_since(conversation_id, offset=summarized_count, db_path=db_path)

    if len(pending_rows) > recent_limit:
        rows_to_summarize = pending_rows[:-recent_limit]
        summary_text = build_summary(
            summary_text,
            [(str(row["role"]), str(row["content"])) for row in rows_to_summarize],
        )
        summarized_count += len(rows_to_summarize)
        db.upsert_agent_summary(
            conversation_id,
            summary_text,
            summarized_count,
            db_path=db_path,
        )
        pending_rows = pending_rows[-recent_limit:]

    prompt_history: list[dict[str, str]] = []
    memory_message = summary_message(summary_text)
    if memory_message is not None:
        prompt_history.append(memory_message)

    prompt_history.extend(
        [
        {"role": str(row["role"]), "content": str(row["content"])}
            for row in pending_rows
        ]
    )
    return prompt_history


def _load_agent_runtime() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    """Import agent runtime components with a clearer dependency error for MCP."""
    try:
        agent_module = import_module("axocare_agent.agent")
        config_module = import_module("axocare_agent.config")
        mcp_client_module = import_module("axocare_agent.mcp_client")
        provider_module = import_module("axocare_agent.provider")
    except ModuleNotFoundError as exc:
        if exc.name == "mcp":
            raise RuntimeError(
                "The Python 'mcp' package is not installed in the active environment. "
                "Reinstall dependencies with 'pip install -r requirements.txt' and restart the API service."
            ) from exc
        raise

    return (
        agent_module.AquariumAgent,
        config_module.AgentConfig,
        mcp_client_module.AxocareMcpClient,
        provider_module.OpenAICompatibleProvider,
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
