"""SQLite persistence and migration helpers for Axocare."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = "axocare.db"
DEFAULT_MIGRATIONS_PATH = Path(__file__).with_name("migrations")


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with row dictionaries and FK checks enabled."""
    path = Path(db_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(
    db_path: str | Path = DEFAULT_DB_PATH,
    migrations_path: str | Path = DEFAULT_MIGRATIONS_PATH,
) -> None:
    """Apply pending SQL migrations in filename order."""
    migrations_dir = Path(migrations_path)
    if not migrations_dir.exists():
        raise FileNotFoundError(f"Migration directory not found: {migrations_dir}")

    with connect(db_path) as conn:
        _ensure_migrations_table(conn)
        applied = _applied_versions(conn)

        for migration in _migration_files(migrations_dir):
            version = _migration_version(migration)
            if version in applied:
                continue

            sql = migration.read_text(encoding="utf-8")
            with conn:
                conn.executescript(sql)
                conn.execute(
                    """
                    INSERT INTO schema_migrations (version, filename)
                    VALUES (?, ?)
                    """,
                    (version, migration.name),
                )


def record_temperature(
    temperature_c: float | None,
    relay_on: bool,
    sensor_id: str | None = None,
    error: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Persist one sensor reading and return its row id."""
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO temperature_readings (
                temperature_c,
                relay_on,
                sensor_id,
                error
            )
            VALUES (?, ?, ?, ?)
            """,
            (temperature_c, int(relay_on), sensor_id, error),
        )
        conn.commit()
        return int(cursor.lastrowid)


def record_relay_event(
    relay_on: bool,
    reason: str,
    *,
    temperature_c: float | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Persist one relay state change and return its row id."""
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO relay_events (
                relay_on,
                reason,
                temperature_c
            )
            VALUES (?, ?, ?)
            """,
            (int(relay_on), reason, temperature_c),
        )
        conn.commit()
        return int(cursor.lastrowid)


def latest_temperatures(
    limit: int = 50,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    """Return recent temperature rows, newest first."""
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT id, recorded_at, temperature_c, relay_on, sensor_id, error
                FROM temperature_readings
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def latest_relay_events(
    limit: int = 50,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    """Return recent relay event rows, newest first."""
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT id, recorded_at, relay_on, reason, temperature_c
                FROM relay_events
                ORDER BY recorded_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            )
        )


def latest_temperature(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> sqlite3.Row | None:
    """Return the newest temperature reading, if one exists."""
    with connect(db_path) as conn:
        return conn.execute("""
            SELECT id, recorded_at, temperature_c, relay_on, sensor_id, error
            FROM temperature_readings
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
            """).fetchone()


def temperatures_since(
    minutes: int,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    """Return temperature readings from the last N minutes, oldest first."""
    with connect(db_path) as conn:
        return list(
            conn.execute(
                """
                SELECT id, recorded_at, temperature_c, relay_on, sensor_id, error
                FROM temperature_readings
                WHERE recorded_at >= datetime('now', ?)
                ORDER BY recorded_at ASC, id ASC
                """,
                (f"-{minutes} minutes",),
            )
        )


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    """Create the migration ledger table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            filename TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """)
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    """Return migration versions already recorded in the ledger."""
    return {
        int(row["version"])
        for row in conn.execute("SELECT version FROM schema_migrations")
    }


def _migration_files(migrations_dir: Path) -> Iterable[Path]:
    """Yield migration SQL files that follow the numeric filename convention."""
    return sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))


def _migration_version(path: Path) -> int:
    """Parse the numeric version prefix from a migration filename."""
    return int(path.name.split("_", 1)[0])
