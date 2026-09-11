"""SQLite-lagring av segmenter."""
from __future__ import annotations

import datetime as dt
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
    waveform     TEXT,
    note         TEXT,
    starred      INTEGER DEFAULT 0,
    origin       TEXT,
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_started_at ON segments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_status ON segments(status);
"""

# Kolonner lagt til etter at folk allerede kjorte appen. Databasen ligger i
# brukerens mappe og overlever oppdateringer, saa den maa oppgraderes paa plass.
MIGRATIONS = {
    "attempts": "INTEGER DEFAULT 0",
    "waveform": "TEXT",
    "note": "TEXT",
    "starred": "INTEGER DEFAULT 0",
    # Filnavnet en opplastet fil kom med. NULL for segmenter fra radioen.
    "origin": "TEXT",
}

# Felter klienten faar lov til aa endre direkte.
EDITABLE = {"text", "translation", "note", "starred"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")     # taaler lesing under skriving
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(segments)")}
        for name, decl in MIGRATIONS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE segments ADD COLUMN {name} {decl}")


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


def stats() -> dict:
    """Tall til statuslinja: totalt, i dag, samlet sendetid."""
    today = dt.date.today().isoformat()
    with _lock, _connect() as conn:
        total, seconds = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration), 0) FROM segments"
        ).fetchone()
        today_n = conn.execute(
            "SELECT COUNT(*) FROM segments WHERE started_at >= ?", (today,)
        ).fetchone()[0]
        starred = conn.execute(
            "SELECT COUNT(*) FROM segments WHERE starred = 1"
        ).fetchone()[0]
    return {"total": total, "today": today_n, "starred": starred,
            "seconds": round(float(seconds), 1)}


def insert_segment(started_at: str, duration: float, wav_path: str,
                   peak_db: float, waveform: str = "[]",
                   origin: str | None = None) -> int:
    with _lock, _connect() as conn:
        cur = conn.execute(
            "INSERT INTO segments (started_at, duration, wav_path, peak_db, waveform,"
            " origin, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')",
            (started_at, duration, wav_path, peak_db, waveform, origin),
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


def list_segments(limit: int = 200, offset: int = 0, search: str = "",
                  status: str = "", starred: bool = False,
                  since: str = "", until: str = "") -> list[dict]:
    sql = "SELECT * FROM segments"
    where: list[str] = []
    params: list = []
    if search:
        where.append("(text LIKE ? OR translation LIKE ? OR note LIKE ?)")
        params += [f"%{search}%"] * 3
    if status:
        where.append("status = ?")
        params.append(status)
    if starred:
        where.append("starred = 1")
    if since:
        where.append("started_at >= ?")
        params.append(since)
    if until:
        where.append("started_at <= ?")
        params.append(until)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [max(1, min(int(limit), 5000)), max(0, int(offset))]
    with _lock, _connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def delete_segment(seg_id: int) -> None:
    seg = get_segment(seg_id)
    if seg:
        Path(seg["wav_path"]).unlink(missing_ok=True)
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM segments WHERE id = ?", (seg_id,))


def delete_all() -> int:
    """Tom loggen helt - bade rader og lydfiler."""
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT wav_path FROM segments").fetchall()
        for row in rows:
            Path(row["wav_path"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM segments")
        return len(rows)


def purge_older_than(days: int) -> int:
    """Slett segmenter eldre enn grensa. 0 betyr behold alt."""
    if days <= 0:
        return 0
    cutoff = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT id, wav_path FROM segments WHERE started_at < ?", (cutoff,)
        ).fetchall()
        for row in rows:
            Path(row["wav_path"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM segments WHERE started_at < ?", (cutoff,))
        return len(rows)
