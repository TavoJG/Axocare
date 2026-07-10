# Axocare MCP Server

This local, read-only MCP server gives compatible AI clients access to Axocare
telemetry without granting them direct SQLite access.

## Install and run

Install the project dependencies, then configure an MCP client to start:

```bash
python -m mcp_server.server --db ./axocare.db
```

For example, an MCP client configuration can use:

```json
{
  "mcpServers": {
    "axocare": {
      "command": "python",
      "args": ["-m", "mcp_server.server", "--db", "/absolute/path/to/axocare.db"]
    }
  }
}
```

The server communicates over stdio. Keep stdout reserved for the MCP protocol.

## Tools

- `get_current_status`
- `get_recent_readings(minutes)` — 1 to 1,440 minutes
- `get_temperature_summary(hours)` — 1 to 168 hours
- `get_relay_events(hours)` — 1 to 168 hours
- `explain_temperature_trend(minutes)` — 1 to 1,440 minutes
- `predict_temperature(horizon_minutes)` — reports unavailable until the local
  AI model is implemented and trained
