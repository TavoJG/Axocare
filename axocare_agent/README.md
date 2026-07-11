# Axocare LLM Agent

The agent answers aquarium questions by invoking the local read-only Axocare
MCP server. It never opens the SQLite database or controls the relay directly.

## Configure

Set an OpenAI-compatible chat-completions endpoint and model in `config.toml`.
The endpoint may be a hosted provider or a compatible local server.

```toml
[database]
path = "./axocare.db"

[agent]
base_url = "http://127.0.0.1:11434/v1"
model = "your-tool-capable-model"
api_key = ""
max_tool_rounds = 6
timeout_seconds = 30
```

## Run

Ask one question:

```bash
python -m axocare_agent.cli --question "How is the aquarium right now?"
```

Or start an interactive session:

```bash
python -m axocare_agent.cli
```

Use `--config /path/to/config.toml` to load a different file. `--base-url`,
`--model`, `--api-key`, and `--db` still override the file for one-off runs.

Use `exit` or `quit` to end an interactive session. The provider must support
OpenAI-style tool calling; the agent discovers the Axocare MCP tools at startup.

For a production Raspberry Pi deployment, run the dashboard API (which exposes
the agent routes) as a systemd service. The sample unit, environment file, and
installation instructions are in
[`deploy/systemd/README.md`](../deploy/systemd/README.md).

## Dashboard API

When the Axocare FastAPI service is running with the same `config.toml`,
the dashboard can call the agent without receiving provider credentials:

```json
POST /api/agent/chat
{
  "question": "How is the aquarium right now?",
  "history": []
}
```

The response is `{ "answer": "..." }`. History accepts up to 12 prior
`user` or `assistant` messages; system and tool messages are not accepted from
the browser.

### Streaming status

`POST /api/agent/chat` is **not streaming**. It waits for the MCP tool calls
and the provider's final response, then returns a single JSON payload. This is
the appropriate first integration for the dashboard, but the browser will not
receive partial text or tool-progress updates.

`POST /api/agent/chat/stream` provides an SSE-shaped integration now. It emits
`status` (`{ "stage": "processing" }`), then either `answer` and `done`, or
an `error` event. It does **not** yet emit token-by-token text because the
current provider adapter waits for the completed chat response.

Use `fetch` and read the response stream for this POST endpoint; the browser's
native `EventSource` API only supports GET requests. Keep the existing JSON
endpoint for clients that do not support SSE.

When provider streaming is added, the backend can forward safe text chunks as
additional `token` events, while keeping provider keys, raw MCP protocol
messages, and SQLite access on the server.

## Safety boundary

- Aquarium data only comes from MCP tool responses.
- The MCP server opens SQLite in read-only mode.
- The agent has no relay, GPIO, migration, or model-training tools.
- Missing data and unavailable predictions are returned to the LLM as explicit
  tool results.
