from __future__ import annotations

import asyncio
from typing import Any

from axocare_agent.agent import AquariumAgent
from axocare_agent.provider import AssistantResponse, ToolCall


def test_agent_executes_mcp_tool_then_returns_grounded_answer() -> None:
    provider = _FakeProvider(
        [
            AssistantResponse(
                content=None,
                tool_calls=[ToolCall("call-1", "get_current_status", "{}")],
            ),
            AssistantResponse(content="The aquarium is currently at 19.4 °C.", tool_calls=[]),
        ]
    )
    mcp = _FakeMcp()

    answer = asyncio.run(AquariumAgent(provider, mcp, max_tool_rounds=3).answer("How is it now?"))

    assert answer == "The aquarium is currently at 19.4 °C."
    assert mcp.calls == [("get_current_status", {})]
    assert provider.messages[1][-1]["content"] == '{"current_temperature_c":19.4}'


def test_agent_returns_structured_tool_error_to_model() -> None:
    provider = _FakeProvider(
        [
            AssistantResponse(
                content=None,
                tool_calls=[ToolCall("call-1", "get_recent_readings", "not-json")],
            ),
            AssistantResponse(content="I could not retrieve the readings.", tool_calls=[]),
        ]
    )

    answer = asyncio.run(AquariumAgent(provider, _FakeMcp(), max_tool_rounds=2).answer("Show history"))

    assert answer == "I could not retrieve the readings."
    assert "Invalid tool arguments" in provider.messages[1][-1]["content"]


def test_agent_includes_runtime_context_in_system_prompt() -> None:
    provider = _FakeProvider([AssistantResponse(content="Objetivo: 18.0 C.", tool_calls=[])])

    answer = asyncio.run(
        AquariumAgent(provider, _FakeMcp(), max_tool_rounds=1).answer(
            "Cual es la temperatura objetivo?",
            system_context="Configured target water temperature: 18.0 C.",
        )
    )

    assert answer == "Objetivo: 18.0 C."
    assert "Support both English" in provider.messages[0][0]["content"]
    assert "Configured target water temperature: 18.0 C." in provider.messages[0][0]["content"]


def test_agent_stops_at_tool_round_limit() -> None:
    provider = _FakeProvider(
        [
            AssistantResponse(None, [ToolCall("one", "get_current_status", "{}")]),
            AssistantResponse(None, [ToolCall("two", "get_current_status", "{}")]),
        ]
    )

    answer = asyncio.run(AquariumAgent(provider, _FakeMcp(), max_tool_rounds=2).answer("Loop"))

    assert "tool-call limit" in answer


class _FakeProvider:
    def __init__(self, responses: list[AssistantResponse]) -> None:
        self._responses = responses
        self.messages: list[list[dict[str, Any]]] = []

    async def complete(self, *, messages, tools) -> AssistantResponse:
        self.messages.append(messages.copy())
        return self._responses.pop(0)


class _FakeMcp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def tool_schemas(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {"name": "get_current_status"}}]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return {"current_temperature_c": 19.4}
