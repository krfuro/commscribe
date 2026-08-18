"""Modellhaandtering: hva er lastet ned, og nedlasting med framdrift.

Forste transkribering med en ny modell henter noen hundre megabyte fra Hugging
Face. Uten framdrift ser appen ut som den har hengt seg, saa vi laster ned
eksplisitt og rapporterer hvor langt den er kommet.
"""
from __future__ import annotations

import shutil
import threading
from pathlib import Path

from .config import MODEL_CATALOG, MODEL_DIR

HUB_DIR = MODEL_DIR / "hub"

_state_lock = threading.Lock()
_downloads: dict[str, dict] = {}     # model_id -> {status, progress, error}


def _repo_dir(model_id: str) -> Path:
    """Hugging Face lagrer <org>/<navn> som models--<org>--<navn>."""
    return HUB_DIR / f"models--{model_id.replace('/', '--')}"


def dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total / (1024 * 1024)


def is_installed(model_id: str) -> bool:
    """Er modellen komplett nedlastet?

    Et avbrutt forsok etterlater .incomplete-filer i blobs/. Vi krever derfor at
    et snapshot finnes og at ingenting er halvveis, ellers ville appen ha meldt
    'installert' om en modell som fortsatt ville lastet ned ved bruk.
    """
    repo = _repo_dir(model_id)
    snapshots = repo / "snapshots"
    if not snapshots.is_dir() or not any(snapshots.iterdir()):
        return False
    blobs = repo / "blobs"
    if blobs.is_dir() and any(blobs.glob("*.incomplete")):
        return False
    return True


def catalog() -> list[dict]:
    """Katalogen slik UI-et ser den, med status per modell."""
    out = []
    for entry in MODEL_CATALOG:
        model_id = entry["id"]
        job = _downloads.get(model_id, {})
        out.append({
            **entry,
            "installed": is_installed(model_id),
            "disk_mb": round(dir_size_mb(_repo_dir(model_id)), 1),
            "status": job.get("status", "idle"),
            "progress": job.get("progress", 0),
            "error": job.get("error"),
        })
    return out


def download_state(model_id: str) -> dict:
    return _downloads.get(model_id, {"status": "idle", "progress": 0})


def _set(model_id: str, **fields) -> None:
    with _state_lock:
        _downloads.setdefault(model_id, {"status": "idle", "progress": 0}).update(fields)


def start_download(model_id: str, on_update=None) -> bool:
    """Start nedlasting i bakgrunnen. Returnerer False hvis den alt gaar."""
    if _downloads.get(model_id, {}).get("status") == "downloading":
        return False
    expected = next((m["size_mb"] for m in MODEL_CATALOG if m["id"] == model_id), 0)
    _set(model_id, status="downloading", progress=0, error=None)

    def notify() -> None:
        if on_update:
            try:
                on_update(model_id, download_state(model_id))
            except Exception as exc:  # noqa: BLE001
                print(f"[models] varsling feilet: {exc}")

    def watcher(stop: threading.Event) -> None:
        """Anslaa framdrift fra hvor mye som ligger paa disk.

        huggingface_hub gir ingen callback vi kan hekte oss paa uten aa kapre
        tqdm, saa vi maaler mappa i stedet. Tallet er omtrentlig, men det er
        framdriftsfolelsen som betyr noe her.
        """
        while not stop.wait(0.7):
            if expected <= 0:
                continue
            pct = min(97, int(dir_size_mb(_repo_dir(model_id)) / expected * 100))
            if pct != _downloads.get(model_id, {}).get("progress"):
                _set(model_id, progress=pct)
                notify()

    def run() -> None:
        stop = threading.Event()
        threading.Thread(target=watcher, args=(stop,), daemon=True).start()
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=model_id,
                cache_dir=str(HUB_DIR),
                allow_patterns=["*.bin", "*.json", "*.txt", "*.model", "*.onnx"],
            )
            _set(model_id, status="installed", progress=100, error=None)
        except Exception as exc:  # noqa: BLE001
            print(f"[models] nedlasting av {model_id} feilet: {exc}")
            _set(model_id, status="error", progress=0, error=str(exc))
        finally:
            stop.set()
            notify()

    threading.Thread(target=run, daemon=True, name=f"dl-{model_id}").start()
    notify()
    return True


def delete(model_id: str) -> bool:
    """Fjern en nedlastet modell for aa frigjore plass."""
    repo = _repo_dir(model_id)
    if not repo.exists():
        return False
    shutil.rmtree(repo, ignore_errors=True)
    _set(model_id, status="idle", progress=0, error=None)
    return True


def disk_usage() -> dict:
    return {"models_mb": round(dir_size_mb(HUB_DIR), 1),
            "path": str(MODEL_DIR)}
