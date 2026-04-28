"""Streamlit dashboard for Axocare temperature readings."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

import db

DEFAULT_CONFIG_PATH = "config.toml"


def load_db_path(config_path: str | Path) -> str:
    """Read the SQLite database path from the TOML configuration file."""
    path = Path(config_path)
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    return str(config.get("database", {}).get("path", db.DEFAULT_DB_PATH))


def rows_to_frame(rows) -> pd.DataFrame:
    """Convert SQLite temperature rows into a chart-friendly DataFrame."""
    frame = pd.DataFrame([dict(row) for row in rows])
    if frame.empty:
        return frame

    frame["recorded_at"] = pd.to_datetime(frame["recorded_at"])
    frame["relay_on"] = frame["relay_on"].astype(bool)
    return frame


def format_temperature(value: float | None) -> str:
    """Format a temperature value for dashboard display."""
    if value is None:
        return "No data"
    return f"{value:.2f} C"


def render_current_reading(row) -> None:
    """Render current temperature, relay state, and sensor status metrics."""
    if row is None:
        st.info("No temperature readings have been recorded yet.")
        return

    temperature_c = row["temperature_c"]
    relay_on = bool(row["relay_on"])
    error = row["error"]

    temp_col, relay_col, status_col = st.columns(3)
    temp_col.metric("Current temperature", format_temperature(temperature_c))
    relay_col.metric("Relay", "On" if relay_on else "Off")
    status_col.metric("Sensor", "Error" if error else "OK")

    st.caption(f"Last reading: {row['recorded_at']}")
    if error:
        st.warning(error)


def render_temperature_chart(frame: pd.DataFrame) -> None:
    """Render the temperature history line chart."""
    if frame.empty:
        st.info("No readings found for the selected time span.")
        return

    chart_data = frame.set_index("recorded_at")[["temperature_c"]]
    st.line_chart(chart_data)

    with st.expander("Recent readings"):
        st.dataframe(
            frame.sort_values("recorded_at", ascending=False),
            hide_index=True,
            use_container_width=True,
        )


def main() -> None:
    """Run the Streamlit dashboard application."""
    st.set_page_config(page_title="Axocare Dashboard", layout="wide")
    st.title("Axocare")

    with st.sidebar:
        st.header("Dashboard")
        span_minutes = st.number_input(
            "Time span (minutes)",
            min_value=5,
            max_value=24 * 60,
            value=60,
            step=5,
        )
        st.caption("Default view shows the last hour.")

    try:
        db_path = load_db_path(DEFAULT_CONFIG_PATH)
        db.migrate(db_path)
        current = db.latest_temperature(db_path=db_path)
        history = rows_to_frame(db.temperatures_since(span_minutes, db_path=db_path))
    except Exception as exc:
        st.error(f"Could not load dashboard data: {exc}")
        return

    st.caption(f"Database: `{db_path}`")
    render_current_reading(current)
    st.subheader(f"Temperature changes in the last {span_minutes} minutes")
    render_temperature_chart(history)


if __name__ == "__main__":
    main()
