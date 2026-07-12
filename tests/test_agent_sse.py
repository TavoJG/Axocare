from __future__ import annotations

import asyncio

import db
from axocare_api import routes


def test_sse_events_include_lifecycle_and_answer(monkeypatch) -> None:
    async def fake_answer_agent(**kwargs) -> str:
        return "The aquarium is stable."

    monkeypatch.setattr(routes, "_answer_agent", fake_answer_agent)
    monkeypatch.setattr(db, "append_agent_messages", lambda *args, **kwargs: None)

    events = asyncio.run(_collect_events())

    assert events == [
        'event: status\ndata: {"stage": "processing", "conversation_id": "conversation-123"}\n\n',
        'event: answer\ndata: {"answer": "The aquarium is stable.", "conversation_id": "conversation-123"}\n\n',
        'event: done\ndata: {}\n\n',
    ]


def test_sse_events_mask_agent_errors(monkeypatch) -> None:
    async def failing_answer_agent(**kwargs) -> str:
        raise RuntimeError("provider key was rejected")

    monkeypatch.setattr(routes, "_answer_agent", failing_answer_agent)

    events = asyncio.run(_collect_events())

    assert events == [
        'event: status\ndata: {"stage": "processing", "conversation_id": "conversation-123"}\n\n',
        'event: error\ndata: {"message": "The aquarium agent is currently unavailable. Check its server configuration."}\n\n',
    ]


async def _collect_events() -> list[str]:
    return [
        event
        async for event in routes._agent_sse_events(
            conversation_id="conversation-123",
            question="How is the aquarium?",
            history=[],
            config_path="/tmp/config.toml",
            db_path="/tmp/axocare.db",
        )
    ]
