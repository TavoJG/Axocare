# Axocare MCP Server

This local, read-only MCP server gives compatible AI clients access to Axocare
telemetry without granting them direct SQLite access.

## Install and run

Install the project dependencies, then configure an MCP client to start:

```bash
python -m mcp_server.server --db ./axocare.db --models-dir ./axocare_ai/models
```

For example, an MCP client configuration can use:

```json
{
  "mcpServers": {
    "axocare": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server",
        "--db",
        "/absolute/path/to/axocare.db",
        "--models-dir",
        "/absolute/path/to/axocare_ai/models"
      ]
    }
  }
}
```

The server communicates over stdio. Keep stdout reserved for the MCP protocol.
It should normally be launched by its MCP client instead of enabled as a
long-running systemd daemon. See [`deploy/systemd/README.md`](../deploy/systemd/README.md)
for the recommended agent service layout and an optional socket-activated MCP
unit template.

## Tools

- `get_current_status`
- `get_recent_readings(minutes)` — 1 to 1,440 minutes
- `get_temperature_summary(hours)` — 1 to 168 hours
- `get_relay_events(hours)` — 1 to 168 hours
- `explain_temperature_trend(minutes)` — 1 to 1,440 minutes
- `predict_temperature(horizon_minutes)` — 10, 15, or 30 minutes, using a
  locally trained model in `axocare_ai/models/`
