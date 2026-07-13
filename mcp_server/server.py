"""Stdio entry point for the local Axocare MCP server."""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from mcp_server import tools

mcp = FastMCP(
    "Axocare Aquarium",
    instructions=(
        "Use these read-only tools to inspect aquarium telemetry. Report missing "
        "or stale data rather than guessing, and describe predictions as estimates."
    ),
    json_response=True,
)

mcp.tool()(tools.get_current_status)
mcp.tool()(tools.get_recent_readings)
mcp.tool()(tools.get_temperature_summary)
mcp.tool()(tools.get_relay_events)
mcp.tool()(tools.predict_temperature)
mcp.tool()(tools.explain_temperature_trend)


def main() -> None:
    """Configure the database then serve MCP messages over standard I/O."""
    parser = argparse.ArgumentParser(description="Run the Axocare MCP server.")
    parser.add_argument(
        "--db",
        default=tools.DEFAULT_DB_PATH,
        help="Path to the Axocare SQLite database (default: axocare.db).",
    )
    parser.add_argument(
        "--models-dir",
        default=tools.DEFAULT_MODELS_DIR,
        help="Path to the directory containing trained temperature models.",
    )
    args = parser.parse_args()
    tools.configure_database(args.db)
    tools.configure_models_dir(args.models_dir)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
