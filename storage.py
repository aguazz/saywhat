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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id               TEXT PRIMARY KEY,
                transcript_id    TEXT NOT NULL,
                created_at       TEXT,
                model_used       TEXT,
                status           TEXT,
                error_msg        TEXT,
                analysis_json    TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id               TEXT PRIMARY KEY,
                analysis_id      TEXT NOT NULL,
                transcript_id    TEXT NOT NULL,
                speaker          TEXT,
                start_ms         INTEGER,
                claim_type       TEXT,
                checkable        INTEGER,
                verdict          TEXT,
                confidence       REAL,
                claim_json       TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verdict_feedback (
                id               TEXT PRIMARY KEY,
                claim_id         TEXT NOT NULL,
                analysis_id      TEXT NOT NULL,
                rating           TEXT,
                user_note        TEXT,
                created_at       TEXT
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


def save_analysis(transcript_id: str, model_used: str) -> str:
    """Create a pending analysis record. Returns the UUID."""
    aid        = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO analyses (id, transcript_id, created_at, model_used, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (aid, transcript_id, created_at, model_used),
        )
    return aid


def complete_analysis(analysis_id: str, analysis_json: dict) -> None:
    """Mark an analysis as complete and store the full result blob."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE analyses
            SET status = 'complete', analysis_json = ?
            WHERE id = ?
            """,
            (json.dumps(analysis_json, ensure_ascii=False), analysis_id),
        )


def fail_analysis(analysis_id: str, error_msg: str) -> None:
    """Mark an analysis as failed and store the error message."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE analyses
            SET status = 'error', error_msg = ?
            WHERE id = ?
            """,
            (error_msg, analysis_id),
        )


def load_analysis(analysis_id: str) -> dict | None:
    """
    Load a full analysis record by UUID.
    Returns None if the ID does not exist.
    analysis_json is parsed back to a dict; all other fields are returned as-is.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    if result.get("analysis_json"):
        result["analysis_json"] = json.loads(result["analysis_json"])
    return result


def load_analysis_for_transcript(transcript_id: str) -> dict | None:
    """
    Return the most recent complete analysis for a transcript, or None.
    analysis_json is parsed back to a dict.
    """
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM analyses
            WHERE transcript_id = ? AND status = 'complete'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (transcript_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    if result.get("analysis_json"):
        result["analysis_json"] = json.loads(result["analysis_json"])
    return result


def save_feedback(claim_id: str, analysis_id: str, rating: str, user_note: str) -> None:
    """Record a user's thumbs-down flag on a claim verdict."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO verdict_feedback (id, claim_id, analysis_id, rating, user_note, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                claim_id,
                analysis_id,
                rating,
                user_note,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


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
