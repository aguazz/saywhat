import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("transcripts.db")


# ---------------------------------------------------------------------------
# Schema — runs once on import
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id                 TEXT PRIMARY KEY,
                title              TEXT,
                created_at         TEXT,
                language           TEXT,
                duration_seconds   REAL,
                transcript_json    TEXT,
                speaker_names_json TEXT
            )
        """)


_init()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_transcript(transcript: dict, speaker_names: dict, title: str) -> str:
    """
    Persist a transcript to the database.
    Returns the UUID that identifies this record (use it to build a shareable link).
    """
    tid        = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO transcripts
                (id, title, created_at, language, duration_seconds,
                 transcript_json, speaker_names_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                title,
                created_at,
                transcript.get("language", "unknown"),
                transcript.get("duration_seconds", 0.0),
                json.dumps(transcript, ensure_ascii=False),
                json.dumps(speaker_names, ensure_ascii=False),
            ),
        )

    return tid


def load_transcript(transcript_id: str) -> dict | None:
    """
    Load a full transcript record by UUID.
    Returns None if the ID does not exist in the database.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM transcripts WHERE id = ?", (transcript_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id":               row["id"],
        "title":            row["title"],
        "created_at":       row["created_at"],
        "language":         row["language"],
        "duration_seconds": row["duration_seconds"],
        "transcript":       json.loads(row["transcript_json"]),
        "speaker_names":    json.loads(row["speaker_names_json"]),
    }


def list_recent(limit: int = 20) -> list[dict]:
    """
    Return the most recent N transcripts (metadata only — no full JSON blob).
    Ordered newest first.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, created_at, language, duration_seconds
            FROM transcripts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]
