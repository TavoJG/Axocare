# Axocare LLM Agent Implementation Plan

## Goal

Build a conversational agent that answers aquarium-monitoring questions using
the local Axocare MCP server. The agent must not access SQLite, GPIO, or the
relay controller directly.

## Architecture

```text
User question
    -> provider-neutral LLM adapter
    -> MCP client / Axocare MCP server
    -> read-only SQLite telemetry and prediction tools
    -> grounded response to the user
```

Implement the agent as a Python package with a small CLI entry point. Keep the
LLM provider behind an adapter so the first integration can use a hosted model
or a local Ollama-compatible endpoint without changing agent behavior.

## Implementation steps

1. Add configuration and CLI
   - Read the selected provider, model name, API/base URL settings, and MCP
     server command from environment variables or explicit CLI arguments.
   - Start the Axocare MCP server as a stdio subprocess using its `--db` path.
   - Never put API keys, database contents, or MCP protocol messages on logs.

2. Implement MCP tool discovery and execution
   - Connect through the official MCP Python client and obtain the server tool
     schemas at startup.
   - Translate provider tool calls into MCP `call_tool` requests and return the
     structured result to the LLM.
   - Surface MCP startup, timeout, invalid-argument, and unavailable-prediction
     failures as clear user-facing limitations.

3. Implement the agent loop
   - Send the user question, system instructions, conversation history, and
     discovered MCP tools to the configured LLM.
   - Continue only while the LLM requests MCP tools; limit tool-call rounds and
     calls per response to prevent loops.
   - Produce a final response only after tool results are available, unless the
     question is explicitly outside aquarium telemetry.

4. Set grounded response policy
   - State current measurements, historical observations, predictions, and
     recommendations as distinct categories.
   - Mention missing, stale, or unavailable data rather than inferring it.
   - Describe forecasts as estimates; do not make veterinary or health claims
     beyond observed temperature-related risk.
   - Ask a brief clarification only when the user’s requested period or metric
     cannot be inferred safely.

5. Add provider adapters
   - Define a common interface for chat completion with tool calling.
   - Implement one adapter first, selected by configuration, then add the
     second provider without changing the MCP or policy layers.
   - Normalize tool-call identifiers, JSON arguments, tool results, and final
     text across adapters.

6. Test and document
   - Unit-test tool-schema translation, argument validation, response policy,
     provider-independent tool-call loops, and all error paths with fakes.
   - Add integration tests against a temporary Axocare SQLite database and the
     real MCP server process.
   - Document setup, provider configuration, example questions, and the
     security boundary that keeps the agent read-only.

## Acceptance criteria

- The agent answers current status, historical temperature, cooling duration,
  relay event, trend, and prediction questions by calling MCP tools.
- It does not fabricate telemetry when no tool result supports an answer.
- It clearly reports missing data and the temporary unavailable-model result.
- Switching LLM providers does not alter MCP tool contracts or aquarium safety
  policy.
