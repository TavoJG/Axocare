from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from axocare_api import routes
from axocare_api.schemas import AgentChatRequest
from axocare_api.settings import ApiSettings


def test_agent_chat_uses_api_database_and_returns_answer(monkeypatch) -> None:
    calls = []

    async def fake_answer_agent(**kwargs) -> str:
        calls.append(kwargs)
        return "The aquarium is stable."

    monkeypatch.setattr(routes, "_answer_agent", fake_answer_agent)
    response = asyncio.run(
        routes.agent_chat(
            AgentChatRequest(
                question="How is it now?",
                history=[{"role": "user", "content": "Show the latest reading."}],
            ),
            _settings(),
        )
    )

    assert response.answer == "The aquarium is stable."
    assert calls == [
        {
            "question": "How is it now?",
            "history": [{"role": "user", "content": "Show the latest reading."}],
            "db_path": "/tmp/axocare.db",
        }
    ]


def test_agent_chat_masks_agent_configuration_errors(monkeypatch) -> None:
    async def failing_answer_agent(**kwargs) -> str:
        raise ValueError("provider configuration missing")

    monkeypatch.setattr(routes, "_answer_agent", failing_answer_agent)

    with pytest.raises(HTTPException) as error:
        asyncio.run(routes.agent_chat(AgentChatRequest(question="How is it now?"), _settings()))

    assert error.value.status_code == 503
    assert error.value.detail == "The aquarium agent is currently unavailable. Check its server configuration."


def _settings() -> ApiSettings:
    return ApiSettings(
        db_path="/tmp/axocare.db",
        target_c=18.0,
        cooling_on_c=18.6,
        cooling_off_c=18.0,
        notification_threshold_c=20.0,
        interval_seconds=60,
    )
