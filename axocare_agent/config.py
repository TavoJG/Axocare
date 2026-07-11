"""Runtime configuration for the Axocare LLM agent."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = "config.toml"


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
    def from_toml(
        cls,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        db_path: str | Path | None = None,
    ) -> "AgentConfig":
        """Read provider settings from config.toml while allowing explicit overrides."""
        path = Path(config_path)
        values = tomllib.loads(path.read_text(encoding="utf-8"))
        agent = values.get("agent", {})
        database = values.get("database", {})

        configured_base_url = base_url or _optional_str(agent.get("base_url"))
        configured_model = model or _optional_str(agent.get("model"))
        if not configured_base_url:
            raise ValueError("Set [agent].base_url in config.toml or pass --base-url.")
        if not configured_model:
            raise ValueError("Set [agent].model in config.toml or pass --model.")

        return cls(
            base_url=configured_base_url.rstrip("/"),
            model=configured_model,
            api_key=api_key if api_key is not None else _optional_str(agent.get("api_key")),
            db_path=str(db_path or database.get("path", "axocare.db")),
            max_tool_rounds=int(agent.get("max_tool_rounds", "6")),
            timeout_seconds=float(agent.get("timeout_seconds", "30")),
        )


def _optional_str(value: object) -> str | None:
    """Return a string while treating blanks as disabled."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
