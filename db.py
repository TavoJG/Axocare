"""SQLite persistence and migration helpers for Axocare."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Iterable
from uuid import uuid4

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
    *,
    room_temperature: float | None = None,
    aht20_humidity_percent: float | None = None,
    bmp280_temperature_c: float | None = None,
    bmp280_pressure_hpa: float | None = None,
    ambient_error: str | None = None,
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
                error,
                room_temperature,
                aht20_humidity_percent,
                bmp280_temperature_c,
                bmp280_pressure_hpa,
                ambient_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                temperature_c,
                int(relay_on),
                sensor_id,
                error,
                room_temperature,
                aht20_humidity_percent,
                bmp280_temperature_c,
                bmp280_pressure_hpa,
                ambient_error,
            ),
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
                SELECT
                    id,
                    recorded_at,
                    temperature_c,
                    relay_on,
                    sensor_id,
                    error,
                    room_temperature,
                    aht20_humidity_percent,
                    bmp280_temperature_c,
                    bmp280_pressure_hpa,
                    ambient_error
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
            SELECT
                id,
                recorded_at,
                temperature_c,
                relay_on,
                sensor_id,
                error,
                room_temperature,
                aht20_humidity_percent,
                bmp280_temperature_c,
                bmp280_pressure_hpa,
                ambient_error
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
                SELECT
                    id,
                    recorded_at,
                    temperature_c,
                    relay_on,
                    sensor_id,
                    error,
                    room_temperature,
                    aht20_humidity_percent,
                    bmp280_temperature_c,
                    bmp280_pressure_hpa,
                    ambient_error
                FROM temperature_readings
                WHERE recorded_at >= datetime('now', ?)
                ORDER BY recorded_at ASC, id ASC
                """,
                (f"-{minutes} minutes",),
            )
        )


def create_agent_conversation(
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str:
    """Create one persisted agent conversation and return its id."""
    conversation_id = str(uuid4())
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_conversations (id)
            VALUES (?)
            """,
            (conversation_id,),
        )
        conn.commit()
    return conversation_id


def agent_conversation_exists(
    conversation_id: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    """Return whether the requested agent conversation exists."""
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM agent_conversations
            WHERE id = ?
            LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()
    return row is not None


def agent_messages(
    conversation_id: str,
    limit: int = 12,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    """Return recent persisted agent messages in chronological order."""
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM (
                SELECT id, role, content, created_at
                FROM agent_messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            )
            ORDER BY created_at ASC, id ASC
            """,
            (conversation_id, limit),
        ).fetchall()
    return list(rows)


def agent_messages_since(
    conversation_id: str,
    offset: int = 0,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> list[sqlite3.Row]:
    """Return agent messages in chronological order after the given offset."""
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM agent_messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT -1 OFFSET ?
            """,
            (conversation_id, offset),
        ).fetchall()
    return list(rows)


def append_agent_messages(
    conversation_id: str,
    messages: Sequence[tuple[str, str]],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Persist one or more agent messages and bump the conversation timestamp."""
    if not messages:
        return

    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO agent_messages (conversation_id, role, content)
            VALUES (?, ?, ?)
            """,
            [(conversation_id, role, content) for role, content in messages],
        )
        conn.execute(
            """
            UPDATE agent_conversations
            SET updated_at = datetime('now')
            WHERE id = ?
            """,
            (conversation_id,),
        )
        conn.commit()


def agent_summary(
    conversation_id: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> sqlite3.Row | None:
    """Return the persisted summary row for one conversation, if present."""
    with connect(db_path) as conn:
        return conn.execute(
            """
            SELECT summary, summarized_message_count
            FROM agent_conversation_summaries
            WHERE conversation_id = ?
            LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()


def upsert_agent_summary(
    conversation_id: str,
    summary: str,
    summarized_message_count: int,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Persist the latest rolling summary for one conversation."""
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO agent_conversation_summaries (
                conversation_id,
                summary,
                summarized_message_count,
                updated_at
            )
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(conversation_id) DO UPDATE SET
                summary = excluded.summary,
                summarized_message_count = excluded.summarized_message_count,
                updated_at = excluded.updated_at
            """,
            (conversation_id, summary, summarized_message_count),
        )
        conn.commit()


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
