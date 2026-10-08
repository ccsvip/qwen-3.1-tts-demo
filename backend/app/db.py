import sqlite3
from datetime import datetime, timezone

from app.config import database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS cloned_voices (
    voice_id TEXT PRIMARY KEY,
    prefix TEXT NOT NULL,
    display_name TEXT NOT NULL,
    target_model TEXT NOT NULL,
    language_hint TEXT,
    source_url TEXT,
    source_filename TEXT,
    created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def upsert_voice(
    *,
    voice_id: str,
    prefix: str,
    display_name: str,
    target_model: str,
    language_hint: str,
    source_url: str,
    source_filename: str,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO cloned_voices (
                voice_id, prefix, display_name, target_model,
                language_hint, source_url, source_filename, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(voice_id) DO UPDATE SET
                prefix = excluded.prefix,
                display_name = excluded.display_name,
                target_model = excluded.target_model,
                language_hint = excluded.language_hint,
                source_url = excluded.source_url,
                source_filename = excluded.source_filename
            """,
            (
                voice_id,
                prefix,
                display_name,
                target_model,
                language_hint,
                source_url,
                source_filename,
                created_at,
            ),
        )


def list_voices() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM cloned_voices ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_voice(voice_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM cloned_voices WHERE voice_id = ?",
            (voice_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_voice(voice_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM cloned_voices WHERE voice_id = ?", (voice_id,))
