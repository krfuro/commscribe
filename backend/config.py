"""Konfigurasjon for Commscribe.

Innstillingene ligger i en JSON-fil i brukerens datamappe og lastes ved oppstart,
slik at appen husker oppsettet mellom okter. API-nokler holdes i en egen fil med
strenge rettigheter og sendes aldri til klienten - UI-et faar bare vite om en
nokkel finnes.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

from .paths import (DATA_DIR, DB_PATH, LOG_DIR, MODEL_DIR, REC_DIR,  # noqa: F401
                    SETTINGS_PATH, WEB_DIR)

load_dotenv()

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)

SECRETS_PATH = DATA_DIR / "secrets.json"
_lock = threading.Lock()

# Modellkatalogen UI-et viser. Storrelsene er nedlastet vekt, ikke minnebruk.
MODEL_CATALOG = [
    {"id": "NbAiLab/nb-whisper-tiny", "label": "Tiny", "size_mb": 75,
     "note": "Raskest. Til svake maskiner eller ren stikkordslogg."},
    {"id": "NbAiLab/nb-whisper-base", "label": "Base", "size_mb": 145,
     "note": "Rask. Grei paa tydelig tale."},
    {"id": "NbAiLab/nb-whisper-small", "label": "Small", "size_mb": 480,
     "note": "Anbefalt. God balanse mellom fart og treffsikkerhet."},
    {"id": "NbAiLab/nb-whisper-medium", "label": "Medium", "size_mb": 1500,
     "note": "Best paa stoyete samband. Krever en kjapp maskin."},
    {"id": "NbAiLab/nb-whisper-large", "label": "Large", "size_mb": 3100,
     "note": "Hoyest kvalitet. Treg uten GPU."},
    {"id": "Systran/faster-whisper-small", "label": "Whisper Small (fler)", "size_mb": 480,
     "note": "OpenAI-vekter. Bruk denne naar sambandet ikke er norsk."},
    {"id": "Systran/faster-whisper-medium", "label": "Whisper Medium (fler)", "size_mb": 1500,
     "note": "OpenAI-vekter, flersprakelig."},
]

MODEL_IDS = {m["id"] for m in MODEL_CATALOG}

LANGUAGES = [
    ("auto", "Automatisk"), ("no", "Norsk"), ("en", "Engelsk"), ("sv", "Svensk"),
    ("da", "Dansk"), ("fi", "Finsk"), ("de", "Tysk"), ("nl", "Nederlandsk"),
    ("fr", "Fransk"), ("es", "Spansk"), ("it", "Italiensk"), ("pl", "Polsk"),
    ("ru", "Russisk"), ("uk", "Ukrainsk"), ("ar", "Arabisk"), ("tr", "Tyrkisk"),
]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class Settings:
    """Kjoretidsinnstillinger. Endres fra UI-et og lagres til disk."""

    # Lyd
    device: int | None = None
    device_name: str = ""              # navnet huskes, indeksen kan flytte seg
    monitor_device: int | None = None
    monitor_enabled: bool = False
    monitor_gain: float = 1.0

    # Transkribering
    stt_engine: str = "local"          # local | api
    stt_model: str = "NbAiLab/nb-whisper-small"
    compute_type: str = "int8"         # int8 | int8_float16 | float16 | float32
    cpu_threads: int = 4
    beam_size: int = 5
    api_provider: str = "groq"         # groq | openai | ollama
    api_model: str = "whisper-large-v3"
    language: str = "auto"

    # Ollama - en spraakmodell paa egen maskin eller paa NOMAD-serveren.
    # Brukes til oversettelse (og etter hvert sammendrag), aldri til lyd:
    # Ollama har ikke noe lydendepunkt, saa STT-motoren "api" krever Groq
    # eller OpenAI. Adressen kommer fra miljoet der bildet setter den
    # (nomad_ollama paa NOMADs docker-nett); ellers er det localhost.
    ollama_url: str = os.getenv("COMMSCRIBE_OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model: str = ""             # tom = forste modell Ollama har

    # Oversettelse
    mode: str = "transcribe"           # transcribe | translate
    target_language: str = "en"
    translate_engine: str = "api"      # api | none

    # Segmentering
    threshold_db: float = -42.0
    min_duration: float = 0.7
    max_duration: float = 30.0
    hangover_ms: int = 700
    preroll_ms: int = 300

    # Oppbevaring
    retention_days: int = 0            # 0 = behold alt
    autostart_capture: bool = False

    # Grensesnitt
    theme: str = "dark"                # dark | light | system
    onboarded: bool = False

    # ---------- validering ----------

    def normalize(self) -> None:
        """Klem verdiene innenfor det maskinvaren og motorene faktisk taaler.

        Innstillingene kommer fra klienten, og en urimelig verdi her ville ellers
        vist seg som en kryptisk feil langt nede i lydtraaden.
        """
        if self.stt_engine not in ("local", "api"):
            self.stt_engine = "local"
        if self.mode not in ("transcribe", "translate"):
            self.mode = "transcribe"
        if self.translate_engine not in ("api", "none"):
            self.translate_engine = "api"
        if self.api_provider not in ("groq", "openai", "ollama"):
            self.api_provider = "groq"
        self.ollama_url = (self.ollama_url or "").strip().rstrip("/")
        if not self.ollama_url.startswith(("http://", "https://")):
            self.ollama_url = os.getenv("COMMSCRIBE_OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = (self.ollama_model or "").strip()

        if self.compute_type not in ("int8", "int8_float16", "float16", "float32"):
            self.compute_type = "int8"
        if self.theme not in ("dark", "light", "system"):
            self.theme = "dark"

        self.cpu_threads = int(_clamp(int(self.cpu_threads or 4), 1, 32))
        self.beam_size = int(_clamp(int(self.beam_size or 5), 1, 10))
        self.threshold_db = _clamp(float(self.threshold_db), -90.0, -5.0)
        self.min_duration = _clamp(float(self.min_duration), 0.1, 10.0)
        self.max_duration = _clamp(float(self.max_duration), 2.0, 120.0)
        self.hangover_ms = int(_clamp(int(self.hangover_ms), 100, 5000))
        self.preroll_ms = int(_clamp(int(self.preroll_ms), 0, 3000))
        self.monitor_gain = _clamp(float(self.monitor_gain), 0.0, 4.0)
        self.retention_days = int(_clamp(int(self.retention_days), 0, 3650))

        if self.device is not None:
            self.device = int(self.device)
        if self.monitor_device is not None:
            self.monitor_device = int(self.monitor_device)

    # ---------- serialisering ----------

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, data: dict) -> None:
        known = {f.name for f in fields(self)}
        for key, value in data.items():
            if key in known:
                setattr(self, key, value)
        self.normalize()
        self.save()

    def save(self) -> None:
        with _lock:
            try:
                tmp = SETTINGS_PATH.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
                tmp.replace(SETTINGS_PATH)   # atomisk, saa fila aldri blir halv
            except OSError as exc:
                print(f"[config] kunne ikke lagre innstillinger: {exc}")

    @classmethod
    def load(cls) -> "Settings":
        inst = cls()
        try:
            if SETTINGS_PATH.exists():
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                for key, value in raw.items():
                    if key in known:
                        setattr(inst, key, value)
        except (OSError, ValueError, TypeError) as exc:
            print(f"[config] ignorerer ugyldig innstillingsfil: {exc}")
        inst.normalize()
        return inst


settings = Settings.load()


# ---------- API-nokler ----------

def _read_secrets() -> dict:
    try:
        if SECRETS_PATH.exists():
            return json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {}


def get_api_key(provider: str) -> str:
    """Nokkel fra lagret fil, ellers fra miljoet (.env eller systemet)."""
    stored = _read_secrets().get(provider, "")
    if stored:
        return stored
    return os.getenv(f"{provider.upper()}_API_KEY", "")


def set_api_key(provider: str, key: str) -> None:
    """Lagre eller fjerne en nokkel. Fila er kun lesbar for eieren."""
    data = _read_secrets()
    if key:
        data[provider] = key
    else:
        data.pop(provider, None)
    with _lock:
        SECRETS_PATH.write_text(json.dumps(data), encoding="utf-8")
        try:
            SECRETS_PATH.chmod(0o600)
        except OSError:
            pass  # Windows bryr seg ikke, og ACL-en der er allerede per bruker


def api_key_status() -> dict:
    """Hva UI-et faar vite: at en nokkel finnes, aldri hva den er."""
    return {p: bool(get_api_key(p)) for p in ("groq", "openai")}


__all__ = [
    "settings", "Settings", "SAMPLE_RATE", "CHANNELS", "FRAME_MS", "FRAME_SIZE",
    "MODEL_CATALOG", "MODEL_IDS", "LANGUAGES", "WEB_DIR", "DATA_DIR", "REC_DIR",
    "MODEL_DIR", "LOG_DIR", "DB_PATH", "get_api_key", "set_api_key", "api_key_status",
]
