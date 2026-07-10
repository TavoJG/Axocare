"""Provider-neutral interface and OpenAI-compatible implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ToolCall:
    """One function invocation requested by a language model."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AssistantResponse:
    """Normalized model response used by the provider-independent agent loop."""

    content: str | None
    tool_calls: list[ToolCall]


class ChatProvider(Protocol):
    """A provider that supports OpenAI-style chat messages and tools."""

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse: ...


class OpenAICompatibleProvider:
    """Chat-completions adapter for hosted or local compatible endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AssistantResponse:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM provider request failed: {exc}") from exc

        try:
            message = response.json()["choices"][0]["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError("LLM provider returned an invalid chat-completions response.") from exc

        calls = [
            ToolCall(
                id=str(call["id"]),
                name=str(call["function"]["name"]),
                arguments=str(call["function"]["arguments"]),
            )
            for call in message.get("tool_calls") or []
        ]
        content = message.get("content")
        return AssistantResponse(content=str(content) if content is not None else None, tool_calls=calls)
