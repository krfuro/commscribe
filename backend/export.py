"""Eksport av sambandsloggen til vanlige filformater."""
from __future__ import annotations

import csv
import datetime as dt
import io
import json

FORMATS = {
    "txt": ("text/plain; charset=utf-8", "txt"),
    "md": ("text/markdown; charset=utf-8", "md"),
    "csv": ("text/csv; charset=utf-8", "csv"),
    "json": ("application/json; charset=utf-8", "json"),
    "srt": ("application/x-subrip; charset=utf-8", "srt"),
}

COLUMNS = ["id", "started_at", "duration", "language", "text", "translation",
           "target_lang", "engine", "status", "peak_db", "note", "starred"]


def _clock(value: str) -> str:
    return (value or "")[11:19] or "--:--:--"


def _parse(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _srt_stamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hrs, rem = divmod(int(seconds), 3600)
    mins, secs = divmod(rem, 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def to_txt(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        lines.append(f"[{_clock(r['started_at'])}] ({float(r['duration']):.1f}s) "
                     f"{r.get('text') or ''}".rstrip())
        if r.get("translation"):
            lines.append(f"{' ' * 11}-> {r['translation']}")
        if r.get("note"):
            lines.append(f"{' ' * 11}# {r['note']}")
    return "\n".join(lines) + ("\n" if lines else "")


def to_markdown(rows: list[dict]) -> str:
    stamp = dt.datetime.now().strftime("%d.%m.%Y %H:%M")
    out = [f"# Sambandslogg\n", f"_Eksportert {stamp} - {len(rows)} transmisjoner_\n"]
    day = None
    for r in rows:
        this_day = (r["started_at"] or "")[:10]
        if this_day != day:
            day = this_day
            out.append(f"\n## {day}\n")
        star = " ★" if r.get("starred") else ""
        out.append(f"**{_clock(r['started_at'])}**{star} · {float(r['duration']):.1f}s · "
                   f"`{(r.get('language') or '??').upper()}`\n")
        out.append(f"{r.get('text') or '_(ingen tale)_'}\n")
        if r.get("translation"):
            out.append(f"> {r['translation']}\n")
        if r.get("note"):
            out.append(f"_Notat: {r['note']}_\n")
    return "\n".join(out)


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k) for k in COLUMNS})
    return buf.getvalue()


def to_srt(rows: list[dict]) -> str:
    """Undertekster med tid regnet fra forste transmisjon i utvalget."""
    origin = None
    for r in rows:
        origin = _parse(r["started_at"])
        if origin:
            break
    if origin is None:
        return ""

    out: list[str] = []
    index = 0
    for r in rows:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        start_dt = _parse(r["started_at"])
        if start_dt is None:
            continue
        index += 1
        start = (start_dt - origin).total_seconds()
        end = start + max(float(r["duration"]), 0.5)
        body = text
        if r.get("translation"):
            body += f"\n{r['translation']}"
        out.append(f"{index}\n{_srt_stamp(start)} --> {_srt_stamp(end)}\n{body}\n")
    return "\n".join(out)


def render(rows: list[dict], fmt: str) -> tuple[str, str]:
    """Returner (innhold, mediatype) for det valgte formatet."""
    fmt = fmt if fmt in FORMATS else "txt"
    media = FORMATS[fmt][0]
    if fmt == "json":
        return json.dumps(rows, ensure_ascii=False, indent=2), media
    if fmt == "csv":
        return to_csv(rows), media
    if fmt == "srt":
        return to_srt(rows), media
    if fmt == "md":
        return to_markdown(rows), media
    return to_txt(rows), media


def filename(fmt: str) -> str:
    ext = FORMATS.get(fmt, FORMATS["txt"])[1]
    return f"commscribe-{dt.datetime.now().strftime('%Y%m%d-%H%M')}.{ext}"
