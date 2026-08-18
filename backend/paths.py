"""Filstier. Skiller mellom program (kun lesing) og brukerdata (skriving).

I en pakket app ligger koden inne i en signert bundle som ikke kan skrives til,
og som byttes ut ved oppdatering. Alt som skal overleve - database, opptak,
innstillinger og nedlastede modeller - maa derfor ligge i brukerens datamappe.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Commscribe"


def is_frozen() -> bool:
    """Kjorer vi fra en PyInstaller-bundle?"""
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Mappa med statiske ressurser som folger programmet (web/, ikoner)."""
    override = os.getenv("COMMSCRIBE_RESOURCE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if is_frozen():
        # PyInstaller pakker ut til _MEIPASS (onefile) eller legger filene ved
        # siden av kjorbaren (onedir). Begge dekkes av dette.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    """Brukerens datamappe, etter plattformens konvensjon."""
    override = os.getenv("COMMSCRIBE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        base = os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_NAME
    base = os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME.lower()


def log_dir() -> Path:
    """Loggmappe. macOS har egen konvensjon; ellers under datamappa."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_NAME
    return data_dir() / "logs"


DATA_DIR = data_dir()
REC_DIR = DATA_DIR / "recordings"
MODEL_DIR = DATA_DIR / "models"
LOG_DIR = log_dir()
DB_PATH = DATA_DIR / "commscribe.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
WEB_DIR = resource_dir() / "web"

for _d in (DATA_DIR, REC_DIR, MODEL_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Hold modellene i vaar egen mappe i stedet for ~/.cache/huggingface. Da vet vi
# hvor de ligger, kan vise storrelsen i UI-et og slette dem derfra.
os.environ.setdefault("HF_HOME", str(MODEL_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(MODEL_DIR / "hub"))

__all__ = [
    "APP_NAME", "DATA_DIR", "REC_DIR", "MODEL_DIR", "LOG_DIR", "DB_PATH",
    "SETTINGS_PATH", "WEB_DIR", "data_dir", "resource_dir", "is_frozen",
]
