"""SQLite-lagring av segmenter."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS segments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    duration     REAL NOT NULL,
    wav_path     TEXT NOT NULL,
    language     TEXT,
    text         TEXT,
    translation  TEXT,
    target_lang  TEXT,
    engine       TEXT,
    status       TEXT DEFAULT 'pending',
    attempts     INTEGER DEFAULT 0,
    peak_db      REAL,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_started_at ON segments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_status ON segments(status);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)
        # Migrering for databaser laget for 'attempts' fantes.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(segments)")}
        if "attempts" not in cols:
            conn.execute("ALTER TABLE segments ADD COLUMN attempts INTEGER DEFAULT 0")


def unfinished_segments() -> list[int]:
    """Segmenter som aldri ble ferdig transkribert.

    Koen ligger i minnet, saa et krasj eller en omstart ville ellers etterlate
    WAV-filer paa disk som aldri blir behandlet. Disse hentes inn igjen ved start.
    """
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id FROM segments WHERE status IN ('pending','processing','retrying')"
            " ORDER BY id ASC"
        ).fetchall()
        return [int(r["id"]) for r in rows]


def count_by_status() -> dict:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) n FROM segments GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


def insert_segment(started_at: str, duration: float, wav_path: str, peak_db: float) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO segments (started_at, duration, wav_path, peak_db, status)"
            " VALUES (?, ?, ?, ?, 'pending')",
            (started_at, duration, wav_path, peak_db),
        )
        return int(cur.lastrowid)


def update_segment(seg_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _connect() as conn:
        conn.execute(f"UPDATE segments SET {cols} WHERE id = ?", (*fields.values(), seg_id))


def get_segment(seg_id: int) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM segments WHERE id = ?", (seg_id,)).fetchone()
        return dict(row) if row else None


def list_segments(limit: int = 200, offset: int = 0, search: str = "") -> list[dict]:
    sql = "SELECT * FROM segments"
    params: list = []
    if search:
        sql += " WHERE text LIKE ? OR translation LIKE ?"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def delete_segment(seg_id: int) -> None:
    seg = get_segment(seg_id)
    if seg:
        Path(seg["wav_path"]).unlink(missing_ok=True)
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM segments WHERE id = ?", (seg_id,))
