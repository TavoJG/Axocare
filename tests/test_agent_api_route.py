from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import db
from axocare_api import routes
from axocare_api.schemas import AgentChatRequest
from axocare_api.settings import ApiSettings


def test_agent_chat_uses_api_database_and_returns_answer(monkeypatch) -> None:
    calls = []
    db_path = "/tmp/axocare.db"
    conversation_id = "conversation-123"

    async def fake_answer_agent(**kwargs) -> str:
        calls.append(kwargs)
        return "The aquarium is stable."

    monkeypatch.setattr(routes, "_answer_agent", fake_answer_agent)
    monkeypatch.setattr(routes, "_prepare_agent_conversation", lambda *args, **kwargs: conversation_id)
    monkeypatch.setattr(routes, "_agent_history", lambda *args, **kwargs: [{"role": "user", "content": "Show the latest reading."}])
    append_calls = []
    monkeypatch.setattr(
        db,
        "append_agent_messages",
        lambda resolved_conversation_id, messages, *, db_path: append_calls.append(
            {
                "conversation_id": resolved_conversation_id,
                "messages": messages,
                "db_path": db_path,
            }
        ),
    )
    response = asyncio.run(
        routes.agent_chat(
            AgentChatRequest(
                question="How is it now?",
                history=[{"role": "user", "content": "Show the latest reading."}],
            ),
            _request(),
            _settings(),
        )
    )

    assert response.answer == "The aquarium is stable."
    assert response.conversation_id == conversation_id
    assert calls == [
        {
            "question": "How is it now?",
            "history": [{"role": "user", "content": "Show the latest reading."}],
            "config_path": "/tmp/config.toml",
            "db_path": db_path,
            "system_context": (
                "Configured target water temperature: 18.0 C.\n"
                "Cooling turns on at: 18.6 C.\n"
                "Cooling turns off at: 18.0 C.\n"
                "Notification threshold: 20.0 C."
            ),
        }
    ]
    assert append_calls == [
        {
            "conversation_id": conversation_id,
            "messages": [("user", "How is it now?"), ("assistant", "The aquarium is stable.")],
            "db_path": db_path,
        }
    ]


def test_agent_chat_masks_agent_configuration_errors(monkeypatch) -> None:
    async def failing_answer_agent(**kwargs) -> str:
        raise ValueError("provider configuration missing")

    monkeypatch.setattr(routes, "_answer_agent", failing_answer_agent)
    monkeypatch.setattr(routes, "_prepare_agent_conversation", lambda *args, **kwargs: "conversation-123")
    monkeypatch.setattr(routes, "_agent_history", lambda *args, **kwargs: [])

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            routes.agent_chat(
                AgentChatRequest(question="How is it now?"),
                _request(),
                _settings(),
            )
        )

    assert error.value.status_code == 503
    assert error.value.detail == routes.AGENT_UNAVAILABLE_MESSAGE


def test_load_agent_runtime_reports_missing_mcp_dependency(monkeypatch) -> None:
    def fake_import_module(name: str):
        if name == "axocare_agent.mcp_client":
            raise ModuleNotFoundError("No module named 'mcp'", name="mcp")
        return SimpleNamespace(
            AquariumAgent=object,
            AgentConfig=object,
            AxocareMcpClient=object,
            OpenAICompatibleProvider=object,
        )

    monkeypatch.setattr(routes, "import_module", fake_import_module)

    with pytest.raises(RuntimeError, match="pip install -r requirements.txt"):
        routes._load_agent_runtime()


def test_agent_system_context_includes_temperature_targets() -> None:
    assert routes._agent_system_context(_settings()) == (
        "Configured target water temperature: 18.0 C.\n"
        "Cooling turns on at: 18.6 C.\n"
        "Cooling turns off at: 18.0 C.\n"
        "Notification threshold: 20.0 C."
    )


def test_prepare_agent_conversation_rejects_unknown_conversation_id(monkeypatch) -> None:
    monkeypatch.setattr(db, "agent_conversation_exists", lambda *args, **kwargs: False)

    with pytest.raises(HTTPException) as error:
        routes._prepare_agent_conversation("missing", [], db_path="/tmp/axocare.db")

    assert error.value.status_code == 404
    assert error.value.detail == "Agent conversation not found."


def _settings() -> ApiSettings:
    return ApiSettings(
        db_path="/tmp/axocare.db",
        target_c=18.0,
        cooling_on_c=18.6,
        cooling_off_c=18.0,
        notification_threshold_c=20.0,
        interval_seconds=60,
    )


def _request() -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config_path="/tmp/config.toml")))
