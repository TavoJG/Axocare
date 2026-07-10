"""Command-line interface for the Axocare LLM agent."""

from __future__ import annotations

import argparse
import asyncio

from axocare_agent.agent import AquariumAgent
from axocare_agent.config import AgentConfig
from axocare_agent.mcp_client import AxocareMcpClient
from axocare_agent.provider import OpenAICompatibleProvider


def main() -> None:
    """Run a one-off question or an interactive aquarium conversation."""
    parser = argparse.ArgumentParser(description="Ask an LLM grounded Axocare questions.")
    parser.add_argument("--db", help="Path to the Axocare SQLite database.")
    parser.add_argument("--base-url", help="OpenAI-compatible provider base URL.")
    parser.add_argument("--model", help="Provider model identifier.")
    parser.add_argument("--api-key", help="Provider API key; defaults to AXOCARE_AGENT_API_KEY.")
    parser.add_argument("--question", help="Answer one question, then exit.")
    args = parser.parse_args()
    config = AgentConfig.from_environment(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        db_path=args.db,
    )
    asyncio.run(_run(config, args.question))


async def _run(config: AgentConfig, question: str | None) -> None:
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
        agent = AquariumAgent(provider, mcp_client, max_tool_rounds=config.max_tool_rounds)
        if question:
            print(await agent.answer(question))
            return

        history: list[dict[str, str]] = []
        while True:
            try:
                user_question = input("You: ").strip()
            except EOFError:
                return
            if user_question.lower() in {"exit", "quit"}:
                return
            if not user_question:
                continue
            response = await agent.answer(user_question, history)
            print(f"Axocare: {response}")
            history.extend(
                [
                    {"role": "user", "content": user_question},
                    {"role": "assistant", "content": response},
                ]
            )


if __name__ == "__main__":
    main()
