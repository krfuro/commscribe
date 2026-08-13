"""Commscribe - FastAPI-backend. Lydfangst, transkribering, oversettelse, live-push."""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import storage
from .audio import AudioCapture, list_devices
from .config import WEB_DIR, settings
from .stt import get_engine, is_hallucination
from .translate import get_translator

# Segmenter som venter paa STT. Bounded slik at en treg motor ikke spiser minnet.
_jobs: queue.Queue = queue.Queue(maxsize=200)
_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_capture: AudioCapture | None = None


def broadcast(event: str, payload: dict) -> None:
    """Kalles fra arbeidstraader - maa gaa via event-loopen."""
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast(event, payload), _loop)


async def _broadcast(event: str, payload: dict) -> None:
    message = json.dumps({"event": event, "data": payload})
    dead = []
    for ws in list(_clients):
        try:
            await ws.send_text(message)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


def on_segment(started_at: str, duration: float, wav_path: str, peak_db: float) -> None:
    """Kalles fra segmenterings-traaden naar en transmisjon er ferdig."""
    seg_id = storage.insert_segment(started_at, duration, wav_path, peak_db)
    row = storage.get_segment(seg_id)
    broadcast("segment_new", row)
    try:
        _jobs.put_nowait(seg_id)
    except queue.Full:
        storage.update_segment(seg_id, status="dropped")
        broadcast("segment_update", storage.get_segment(seg_id))


def pipeline_worker() -> None:
    """Tar segmenter fra koen, transkriberer og oversetter."""
    while True:
        seg_id = _jobs.get()
        if seg_id is None:
            break
        seg = storage.get_segment(seg_id)
        if not seg:
            continue

        storage.update_segment(seg_id, status="processing")
        broadcast("segment_update", storage.get_segment(seg_id))

        try:
            engine = get_engine(settings.stt_engine,
                                settings.stt_model if settings.stt_engine == "local"
                                else settings.api_model)
            task = "translate" if (settings.mode == "translate"
                                   and settings.target_language == "en") else "transcribe"
            result = engine.transcribe(seg["wav_path"], settings.language, task)

            if is_hallucination(result.text):
                storage.update_segment(seg_id, status="empty", text="",
                                       language=result.language, engine=result.engine)
                broadcast("segment_update", storage.get_segment(seg_id))
                continue

            fields = {"text": result.text, "language": result.language,
                      "engine": result.engine, "status": "done"}

            # Whisper oversetter kun til engelsk. Andre maalsprak gaar via eget ledd.
            needs_translation = (settings.mode == "translate"
                                 and settings.target_language != result.language
                                 and task != "translate")
            if needs_translation:
                translator = get_translator(settings.translate_engine)
                fields["translation"] = translator.translate(
                    result.text, result.language, settings.target_language)
                fields["target_lang"] = settings.target_language

            storage.update_segment(seg_id, **fields)
        except Exception as exc:  # noqa: BLE001
            print(f"[pipeline] feil paa segment {seg_id}: {exc}")
            storage.update_segment(seg_id, status="error", text=f"[feil] {exc}")

        broadcast("segment_update", storage.get_segment(seg_id))


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _loop, _capture
    _loop = asyncio.get_running_loop()
    storage.init_db()
    _capture = AudioCapture(on_segment=on_segment)
    threading.Thread(target=pipeline_worker, daemon=True).start()
    print("[commscribe] klar paa http://127.0.0.1:8420")
    yield
    if _capture and _capture.is_running:
        _capture.stop()


app = FastAPI(title="Commscribe", lifespan=lifespan)


@app.get("/api/devices")
def api_devices():
    return list_devices()


@app.get("/api/config")
def api_get_config():
    return settings.to_dict()


@app.post("/api/config")
async def api_set_config(payload: dict):
    settings.update(payload)
    return settings.to_dict()


@app.get("/api/status")
def api_status():
    return {
        "running": bool(_capture and _capture.is_running),
        "level_db": round(_capture.level_db, 1) if _capture else -120.0,
        "active": bool(_capture and _capture.active),
        "queue": _jobs.qsize(),
    }


@app.post("/api/start")
def api_start(payload: dict | None = None):
    if payload:
        settings.update(payload)
    try:
        _capture.start(settings.device)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    broadcast("status", {"running": True})
    return {"running": True}


@app.post("/api/stop")
def api_stop():
    _capture.stop()
    broadcast("status", {"running": False})
    return {"running": False}


@app.get("/api/segments")
def api_segments(limit: int = 200, offset: int = 0, q: str = ""):
    return storage.list_segments(limit=limit, offset=offset, search=q)


@app.get("/api/segments/{seg_id}/audio")
def api_audio(seg_id: int):
    seg = storage.get_segment(seg_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment finnes ikke")
    return FileResponse(seg["wav_path"], media_type="audio/wav")


@app.delete("/api/segments/{seg_id}")
def api_delete(seg_id: int):
    storage.delete_segment(seg_id)
    return {"deleted": seg_id}


@app.get("/api/export")
def api_export(fmt: str = "txt", q: str = ""):
    rows = storage.list_segments(limit=10000, search=q)
    rows.reverse()
    if fmt == "json":
        return rows
    lines = []
    for r in rows:
        stamp = (r["started_at"] or "")[11:19]
        line = f"[{stamp}] ({r['duration']:.1f}s) {r['text'] or ''}"
        if r["translation"]:
            line += f"\n           -> {r['translation']}"
        lines.append(line)
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse("\n".join(lines))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await asyncio.sleep(0.5)
            if _capture:
                await ws.send_text(json.dumps({
                    "event": "level",
                    "data": {"db": round(_capture.level_db, 1),
                             "active": _capture.active,
                             "running": _capture.is_running},
                }))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
