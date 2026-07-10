"""Grounded tool-calling loop for Axocare aquarium questions."""

from __future__ import annotations

import json
from typing import Any, Protocol

from axocare_agent.provider import AssistantResponse, ChatProvider

SYSTEM_INSTRUCTIONS = """You are Axocare's aquarium monitoring assistant.
Use the provided MCP tools for aquarium telemetry instead of guessing. Clearly
distinguish current measurements, historical observations, predictions, and
recommendations. Mention missing, stale, or unavailable data. Predictions are
estimates, not certainties. Do not make veterinary or health claims beyond an
observed temperature-related risk. Do not claim a tool result that you did not
receive."""


class ToolClient(Protocol):
    """Minimal MCP interface used by the agent loop and test fakes."""

    async def tool_schemas(self) -> list[dict[str, Any]]: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class AquariumAgent:
    """Coordinate a chat provider and MCP tools to answer one user question."""

    def __init__(self, provider: ChatProvider, mcp_client: ToolClient, *, max_tool_rounds: int) -> None:
        self._provider = provider
        self._mcp_client = mcp_client
        self._max_tool_rounds = max_tool_rounds

    async def answer(
        self,
        question: str,
        history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Answer a question, executing only MCP tools requested by the model."""
        tools = await self._mcp_client.tool_schemas()
        messages = [{"role": "system", "content": SYSTEM_INSTRUCTIONS}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": question})

        for _ in range(self._max_tool_rounds):
            response = await self._provider.complete(messages=messages, tools=tools)
            if not response.tool_calls:
                return response.content or "I could not produce a response."
            messages.append(_assistant_tool_message(response))
            for call in response.tool_calls:
                result = await self._execute_tool(call.name, call.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, separators=(",", ":")),
                    }
                )

        return (
            "I could not complete the request because the tool-call limit was reached. "
            "Please ask a narrower aquarium question."
        )

    async def _execute_tool(self, name: str, arguments_json: str) -> dict[str, Any]:
        try:
            arguments = json.loads(arguments_json)
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object.")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return {"available": False, "error": f"Invalid tool arguments for {name}: {exc}"}

        try:
            return await self._mcp_client.call_tool(name, arguments)
        except Exception as exc:  # Provider needs a structured tool failure to recover.
            return {"available": False, "error": f"MCP tool {name} failed: {exc}"}


def _assistant_tool_message(response: AssistantResponse) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": response.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in response.tool_calls
        ],
    }
