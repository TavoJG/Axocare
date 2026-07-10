"""Async client for the local Axocare stdio MCP server."""

from __future__ import annotations

import asyncio
import sys
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class AxocareMcpClient:
    """Launch and communicate with the local MCP server over stdio."""

    def __init__(self, db_path: str, *, startup_timeout_seconds: float = 15.0) -> None:
        self._parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server", "--db", db_path],
            cwd=Path(__file__).resolve().parents[1],
        )
        self._transport: AbstractAsyncContextManager | None = None
        self._session_context: AbstractAsyncContextManager | None = None
        self._session: ClientSession | None = None
        self._startup_timeout_seconds = startup_timeout_seconds

    async def __aenter__(self) -> "AxocareMcpClient":
        try:
            self._transport = stdio_client(self._parameters)
            read_stream, write_stream = await self._transport.__aenter__()
            self._session_context = ClientSession(read_stream, write_stream)
            self._session = await self._session_context.__aenter__()
            async with asyncio.timeout(self._startup_timeout_seconds):
                await self._session.initialize()
            return self
        except Exception as exc:
            await self.__aexit__(type(exc), exc, exc.__traceback__)
            raise RuntimeError(f"Could not initialize the Axocare MCP server: {exc}") from exc

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        if self._session_context is not None:
            await self._session_context.__aexit__(exc_type, exc_value, traceback)
        if self._transport is not None:
            await self._transport.__aexit__(exc_type, exc_value, traceback)

    async def tool_schemas(self) -> list[dict[str, Any]]:
        """Return discovered MCP tools in OpenAI-compatible function format."""
        session = self._require_session()
        result = await session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call one MCP tool and return its complete JSON-safe result."""
        result = await self._require_session().call_tool(name, arguments)
        return result.model_dump(mode="json")

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("The MCP client is not connected.")
        return self._session
