"""Runtime configuration for the Axocare LLM agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    """Configuration for an OpenAI-compatible chat-completions provider."""

    base_url: str
    model: str
    api_key: str | None
    db_path: str
    max_tool_rounds: int = 6
    timeout_seconds: float = 30.0

    @classmethod
    def from_environment(
        cls,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        db_path: str | Path | None = None,
    ) -> "AgentConfig":
        """Read provider settings while allowing explicit CLI overrides."""
        configured_base_url = base_url or os.getenv("AXOCARE_AGENT_BASE_URL")
        configured_model = model or os.getenv("AXOCARE_AGENT_MODEL")
        if not configured_base_url:
            raise ValueError("Set AXOCARE_AGENT_BASE_URL or pass --base-url.")
        if not configured_model:
            raise ValueError("Set AXOCARE_AGENT_MODEL or pass --model.")

        return cls(
            base_url=configured_base_url.rstrip("/"),
            model=configured_model,
            api_key=api_key if api_key is not None else os.getenv("AXOCARE_AGENT_API_KEY"),
            db_path=str(db_path or os.getenv("AXOCARE_AGENT_DB", "axocare.db")),
            max_tool_rounds=int(os.getenv("AXOCARE_AGENT_MAX_TOOL_ROUNDS", "6")),
            timeout_seconds=float(os.getenv("AXOCARE_AGENT_TIMEOUT_SECONDS", "30")),
        )
