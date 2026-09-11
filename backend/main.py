"""Commscribe - FastAPI-backend. Lydfangst, transkribering, oversettelse, live-push."""
from __future__ import annotations

import asyncio
import json
import os
import queue
import shutil
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (FastAPI, File, Form, HTTPException, Request, UploadFile,
                     WebSocket, WebSocketDisconnect)
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import export, models, storage, upload
from .audio import AUDIO_ERROR, AudioCapture, list_devices
from .config import (DATA_DIR, LANGUAGES, LOG_DIR, MODEL_CATALOG, REC_DIR, UI_LANGUAGES,
                     WEB_DIR, api_key_status, get_api_key, set_api_key, settings)
from .i18n import t
from .paths import is_container
from .stt import get_engine, is_hallucination, unload_local
from .translate import get_translator, ollama_models

APP_VERSION = "1.1.0"

# Segmenter som venter paa STT. Bounded slik at en treg motor ikke spiser minnet.
_jobs: queue.Queue = queue.Queue(maxsize=500)
_clients: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_capture: AudioCapture | None = None
_started = time.time()

MAX_ATTEMPTS = 3
# Deles med klienten slik at frontenden ikke maa gjette paa grensa.
AUTH_TOKEN = ""


# ---------- utsending ----------

def broadcast(event: str, payload: dict) -> None:
    """Kalles fra arbeidstraader - maa gaa via event-loopen."""
    if _loop is None or _loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(_broadcast(event, payload), _loop)
    except RuntimeError:
        pass  # loopen er paa vei ned


async def _broadcast(event: str, payload: dict) -> None:
    message = json.dumps({"event": event, "data": payload}, ensure_ascii=False)
    dead = []
    for ws in list(_clients):
        try:
            await ws.send_text(message)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


def broadcast_queue() -> None:
    """Dytt kodybden ut slik at UI-et viser etterslepet."""
    broadcast("queue", {"depth": _jobs.qsize()})


def notify(level: str, message: str) -> None:
    """Melding til brukeren i UI-et (info | warn | error)."""
    broadcast("notice", {"level": level, "message": message})


def on_capture_error(message: str, fatal: bool = False) -> None:
    if _capture is not None:
        _capture.last_error = message
    notify("error" if fatal else "warn", message)


# ---------- behandlingskoen ----------

def on_segment(started_at: str, duration: float, wav_path: str, peak_db: float,
               waveform: str = "[]", origin: str | None = None) -> int:
    """Kalles fra segmenterings-traaden naar en transmisjon er ferdig - og fra
    opplastingsruta, som gaar samme vei inn.

    WAV-en ligger allerede paa disk her. Transkribering skjer asynkront, saa
    opptaket gaar aldri tapt selv om STT henger eller feiler.
    """
    seg_id = storage.insert_segment(started_at, duration, wav_path, peak_db, waveform,
                                    origin=origin)
    broadcast("segment_new", storage.get_segment(seg_id))
    enqueue(seg_id)
    return seg_id


def capabilities() -> dict:
    """Hva denne installasjonen kan - grensesnittet tegner seg etter det.

    I en container finnes det ingen lydenhet: da skjules lyttingen og
    opplasting blir hovedinngangen. Fakta, ikke en "modus": et skrivebord uten
    PortAudio skal oppfore seg likt.
    """
    return {
        "capture": AUDIO_ERROR is None,
        "capture_error": AUDIO_ERROR,
        "upload": True,
        "container": is_container(),
        "upload_accept": list(upload.ACCEPTED),
    }


def enqueue(seg_id: int) -> bool:
    try:
        _jobs.put_nowait(seg_id)
    except queue.Full:
        storage.update_segment(seg_id, status="dropped")
        broadcast("segment_update", storage.get_segment(seg_id))
        notify("warn", t("queue_full"))
        return False
    broadcast_queue()
    return True


def _process(seg_id: int) -> None:
    """Transkriber og oversett ett segment. Feil haandteres av kalleren."""
    seg = storage.get_segment(seg_id)
    if not seg:
        return

    model = settings.stt_model if settings.stt_engine == "local" else settings.api_model
    engine = get_engine(settings.stt_engine, model)

    # Whisper kan oversette internt, men kun til engelsk. Da sparer vi et ledd.
    task = ("translate" if settings.mode == "translate"
            and settings.target_language == "en" else "transcribe")
    result = engine.transcribe(seg["wav_path"], settings.language, task)

    if is_hallucination(result.text):
        storage.update_segment(seg_id, status="empty", text="",
                               language=result.language, engine=result.engine)
        return

    fields = {"text": result.text, "language": result.language,
              "engine": result.engine, "status": "done"}

    needs_translation = (settings.mode == "translate"
                         and settings.translate_engine != "none"
                         and settings.target_language != result.language
                         and task != "translate")
    if needs_translation:
        translator = get_translator(settings.translate_engine)
        fields["translation"] = translator.translate(
            result.text, result.language, settings.target_language)
        fields["target_lang"] = settings.target_language

    storage.update_segment(seg_id, **fields)


def pipeline_worker() -> None:
    """Tar segmenter fra koen, transkriberer og oversetter."""
    while True:
        seg_id = _jobs.get()
        if seg_id is None:
            break
        broadcast_queue()
        seg = storage.get_segment(seg_id)
        if not seg:
            continue

        attempts = (seg.get("attempts") or 0) + 1
        storage.update_segment(seg_id, status="processing", attempts=attempts)
        broadcast("segment_update", storage.get_segment(seg_id))

        try:
            _process(seg_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[pipeline] feil paa segment {seg_id} (forsok {attempts}): {exc}")
            if attempts < MAX_ATTEMPTS:
                # Nettverksglipp og modell-lasting kan feile forbigaaende.
                # WAV-en ligger trygt paa disk, saa vi kan prove igjen.
                storage.update_segment(seg_id, status="retrying",
                                       text=t("attempt", n=attempts, max=MAX_ATTEMPTS, err=exc))
                broadcast("segment_update", storage.get_segment(seg_id))
                threading.Timer(2.0 * attempts, enqueue, args=(seg_id,)).start()
                continue
            storage.update_segment(seg_id, status="error", text=t("failed", err=exc))
            notify("error", t("transcription_failed", err=exc))

        broadcast("segment_update", storage.get_segment(seg_id))
        broadcast_queue()


async def level_ticker() -> None:
    """Sender nivaamaalingen jevnt, i stedet for en lokke per tilkobling."""
    while True:
        await asyncio.sleep(0.1)
        if not _clients or _capture is None:
            continue
        await _broadcast("level", {
            "db": round(_capture.level_db, 1),
            "peak": round(_capture.peak_db, 1),
            "active": _capture.active,
            "running": _capture.is_running,
            "clipping": _capture.clipping,
        })


# ---------- livssyklus ----------

@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    global _loop, _capture
    _loop = asyncio.get_running_loop()
    storage.init_db()
    _capture = AudioCapture(on_segment=on_segment, on_error=on_capture_error)
    threading.Thread(target=pipeline_worker, daemon=True,
                     name="commscribe-pipeline").start()
    ticker = asyncio.create_task(level_ticker())

    removed = storage.purge_older_than(settings.retention_days)
    if removed:
        print(f"[commscribe] slettet {removed} segmenter eldre enn "
              f"{settings.retention_days} dager")

    # Hent inn segmenter som ikke rakk aa bli behandlet for forrige avslutning.
    orphans = storage.unfinished_segments()
    for seg_id in orphans:
        enqueue(seg_id)
    if orphans:
        print(f"[commscribe] gjenopptar {len(orphans)} ubehandlede segmenter")

    if settings.autostart_capture:
        try:
            _capture.start(settings.device)
            print("[commscribe] lytting startet automatisk")
        except Exception as exc:  # noqa: BLE001
            print(f"[commscribe] autostart feilet: {exc}")

    print(f"[commscribe] klar (data i {DATA_DIR})")
    yield

    ticker.cancel()
    if _capture and _capture.is_running:
        _capture.stop()


app = FastAPI(title="Commscribe", version=APP_VERSION, lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


# ---------- adgangskontroll ----------

@app.middleware("http")
async def guard(request: Request, call_next):
    """Slipp bare inn kall som kjenner okt-nokkelen.

    Serveren lytter kun paa 127.0.0.1, men det holder ikke alene: en hvilken som
    helst nettside i nettleseren kan sende foresporsler dit. Nokkelen gis til
    vinduet vaart ved oppstart og foreligger ingen andre steder.
    """
    path = request.url.path
    if AUTH_TOKEN and path.startswith(("/api", "/ws")):
        given = (request.headers.get("x-commscribe-token")
                 or request.query_params.get("token", ""))
        if given != AUTH_TOKEN:
            return JSONResponse({"detail": t("bad_token")}, status_code=401)
    return await call_next(request)


# ---------- oppsett ----------

@app.get("/health")
def api_health():
    """Aapen med vilje: skallet poller denne for aa vite naar serveren er oppe."""
    return {"ok": True, "version": APP_VERSION, "uptime": round(time.time() - _started, 1)}


@app.get("/api/devices")
def api_devices():
    return list_devices()


@app.get("/api/config")
def api_get_config():
    return {**settings.to_dict(), "api_keys": api_key_status(),
            "languages": LANGUAGES, "models": MODEL_CATALOG,
            "version": APP_VERSION, "data_dir": str(DATA_DIR),
            "log_dir": str(LOG_DIR), "capabilities": capabilities(),
            "ui_languages": UI_LANGUAGES}



@app.post("/api/config")
async def api_set_config(payload: dict):
    previous_model = (settings.stt_model, settings.compute_type, settings.cpu_threads)
    settings.update(payload)

    # Bytter brukeren modell, skal den gamle ut av minnet med en gang - ellers
    # ligger flere hundre megabyte igjen uten aa bli brukt.
    if (settings.stt_model, settings.compute_type, settings.cpu_threads) != previous_model:
        unload_local()

    # Medlytt skal kunne slaas av og paa mens det gaar.
    if _capture:
        _capture.set_monitor(settings.monitor_enabled, settings.monitor_device)

    broadcast("config", settings.to_dict())
    return settings.to_dict()


@app.post("/api/keys")
def api_set_key(payload: dict):
    provider = payload.get("provider", "")
    if provider not in ("groq", "openai"):
        raise HTTPException(status_code=400, detail=t("unknown_provider"))
    set_api_key(provider, (payload.get("key") or "").strip())
    return api_key_status()


def _test_ollama() -> dict:
    """Ollama har ingen nokkel aa teste - vi sporr om den svarer og har modeller."""
    import httpx

    try:
        names = ollama_models(settings.ollama_url)
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": t("ollama_unreachable", url=settings.ollama_url, err=exc)}
    if not names:
        return {"ok": False, "detail": t("ollama_no_models")}
    chosen = settings.ollama_model
    if chosen and chosen not in names and not any(n.startswith(chosen + ":") for n in names):
        return {"ok": False, "detail": t("ollama_missing_model", model=chosen,
                                         models=", ".join(names[:6]))}
    return {"ok": True, "detail": t("ollama_ok", n=len(names), models=", ".join(names[:6]))}


@app.post("/api/keys/test")
def api_test_key(payload: dict):
    """Sjekk at nokkelen faktisk virker, sa brukeren slipper aa oppdage det
    forst naar en transmisjon feiler."""
    import httpx

    provider = payload.get("provider", settings.api_provider)
    if provider == "ollama":
        return _test_ollama()
    key = get_api_key(provider)
    if not key:
        return {"ok": False, "detail": t("no_key")}
    url = ("https://api.groq.com/openai/v1/models" if provider == "groq"
           else "https://api.openai.com/v1/models")
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
    except httpx.HTTPError as exc:
        return {"ok": False, "detail": t("unreachable", provider=provider, err=exc)}
    if resp.status_code == 200:
        return {"ok": True, "detail": t("key_ok")}
    return {"ok": False, "detail": t("key_rejected", code=resp.status_code)}


@app.get("/api/status")
def api_status():
    return {
        "running": bool(_capture and _capture.is_running),
        "level_db": round(_capture.level_db, 1) if _capture else -120.0,
        "peak_db": round(_capture.peak_db, 1) if _capture else -120.0,
        "active": bool(_capture and _capture.active),
        "clipping": bool(_capture and _capture.clipping),
        "queue": _jobs.qsize(),
        "queue_max": _jobs.maxsize,
        "clients": len(_clients),
        "error": _capture.last_error if _capture else None,
        "counts": storage.count_by_status(),
        "stats": storage.stats(),
        "engine": settings.stt_engine,
        "model": settings.stt_model,
        "capabilities": capabilities(),
    }


# ---------- lytting ----------

@app.post("/api/start")
def api_start(payload: dict | None = None):
    if payload:
        settings.update(payload)
    if _capture is None:
        raise HTTPException(status_code=503, detail=t("audio_not_ready"))
    try:
        _capture.start(settings.device)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    broadcast("status", {"running": True})
    return {"running": True}


@app.post("/api/stop")
def api_stop():
    if _capture:
        _capture.stop()
    broadcast("status", {"running": False})
    return {"running": False}


@app.post("/api/peak/reset")
def api_reset_peak():
    if _capture:
        _capture.reset_peak()
    return {"ok": True}


# ---------- opplasting ----------

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), started_at: str = Form("")):
    """Ta imot en lydfil og legg den i koen som ett segment.

    Fila strommes til en midlertidig fil i opptaksmappa (samme disk, saa
    flyttingen etterpaa er gratis) og dekodes derfra. Alt tungt skjer i
    en arbeidstraad: FastAPI kjorer `ingest` utenfor event-loopen.
    """
    name = Path(file.filename or "opplastet").name
    REC_DIR.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(prefix="opplasting-", suffix=Path(name).suffix,
                                      dir=REC_DIR, delete=False)
    tmp_path = Path(tmp.name)
    try:
        with tmp:
            while chunk := await file.read(1 << 20):
                tmp.write(chunk)
        when = upload.parse_started_at(started_at)
        seg = await asyncio.to_thread(upload.ingest, tmp_path, name, when)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    seg_id = on_segment(seg["started_at"], seg["duration"], seg["wav_path"],
                        seg["peak_db"], seg["waveform"], origin=seg["origin"])
    return storage.get_segment(seg_id)



# ---------- segmenter ----------

@app.get("/api/segments")
def api_segments(limit: int = 200, offset: int = 0, q: str = "",
                 status: str = "", starred: bool = False):
    return storage.list_segments(limit=limit, offset=offset, search=q,
                                 status=status, starred=starred)


@app.get("/api/segments/{seg_id}/audio")
def api_audio(seg_id: int):
    seg = storage.get_segment(seg_id)
    if not seg:
        raise HTTPException(status_code=404, detail=t("unknown_segment"))
    if not Path(seg["wav_path"]).exists():
        raise HTTPException(status_code=410, detail=t("audio_gone"))
    return FileResponse(seg["wav_path"], media_type="audio/wav")


@app.patch("/api/segments/{seg_id}")
def api_patch(seg_id: int, payload: dict):
    """Rett opp transkripsjonen eller legg ved et notat."""
    if not storage.get_segment(seg_id):
        raise HTTPException(status_code=404, detail=t("unknown_segment"))
    fields = {k: v for k, v in payload.items() if k in storage.EDITABLE}
    if not fields:
        raise HTTPException(status_code=400, detail=t("nothing_to_change"))
    if "starred" in fields:
        fields["starred"] = 1 if fields["starred"] else 0
    storage.update_segment(seg_id, **fields)
    row = storage.get_segment(seg_id)
    broadcast("segment_update", row)
    return row


@app.post("/api/segments/{seg_id}/retry")
def api_retry(seg_id: int):
    seg = storage.get_segment(seg_id)
    if not seg:
        raise HTTPException(status_code=404, detail=t("unknown_segment"))
    storage.update_segment(seg_id, status="pending", attempts=0, text=None)
    enqueue(seg_id)
    broadcast("segment_update", storage.get_segment(seg_id))
    return {"queued": seg_id}


@app.delete("/api/segments/{seg_id}")
def api_delete(seg_id: int):
    storage.delete_segment(seg_id)
    broadcast("segment_deleted", {"id": seg_id})
    return {"deleted": seg_id}


@app.post("/api/segments/clear")
def api_clear():
    removed = storage.delete_all()
    broadcast("cleared", {"removed": removed})
    return {"removed": removed}


# ---------- modeller ----------

@app.get("/api/models")
def api_models():
    return {"models": models.catalog(), **models.disk_usage()}


@app.post("/api/models/{org}/{name}/download")
def api_model_download(org: str, name: str):
    model_id = f"{org}/{name}"
    if model_id not in {m["id"] for m in MODEL_CATALOG}:
        raise HTTPException(status_code=404, detail=t("unknown_model"))


    def on_update(mid: str, state: dict) -> None:
        broadcast("model", {"id": mid, **state})

    started = models.start_download(model_id, on_update)
    return {"started": started, **models.download_state(model_id)}


@app.delete("/api/models/{org}/{name}")
def api_model_delete(org: str, name: str):
    model_id = f"{org}/{name}"
    if model_id == settings.stt_model:
        unload_local()
    return {"deleted": models.delete(model_id)}


# ---------- eksport ----------

@app.get("/api/export")
def api_export(fmt: str = "txt", q: str = "", starred: bool = False):
    rows = storage.list_segments(limit=5000, search=q, starred=starred)
    rows.reverse()      # eldst forst leses som en logg
    body, media = export.render(rows, fmt)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition":
                 f'attachment; filename="{export.filename(fmt)}"'},
    )


# ---------- live ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if AUTH_TOKEN and ws.query_params.get("token") != AUTH_TOKEN:
        await ws.close(code=4401)
        return
    await ws.accept()
    _clients.add(ws)
    try:
        await ws.send_text(json.dumps({"event": "hello",
                                       "data": {"version": APP_VERSION}}))
        while True:
            # Vi trenger ingenting fra klienten, men maa lese for aa oppdage
            # at den forsvinner. Nivaamaalingen sendes av level_ticker.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        pass
    finally:
        _clients.discard(ws)


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
else:  # pragma: no cover - bare hvis pakkingen har mistet web-mappa
    print(f"[commscribe] fant ikke web-mappa: {WEB_DIR}")


def configure(token: str = "") -> None:
    """Settes av oppstartsskriptet for uvicorn starter."""
    global AUTH_TOKEN
    AUTH_TOKEN = token or os.getenv("COMMSCRIBE_TOKEN", "")
