"""Konfigurasjon for Commscribe."""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REC_DIR = DATA_DIR / "recordings"
DB_PATH = DATA_DIR / "commscribe.db"
WEB_DIR = ROOT / "web"

DATA_DIR.mkdir(exist_ok=True)
REC_DIR.mkdir(exist_ok=True)

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_MS = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_MS / 1000)


@dataclass
class Settings:
    """Kjoretidsinnstillinger som kan endres fra UI."""

    device: int | None = None
    monitor_device: int | None = None
    monitor_enabled: bool = False

    # STT
    stt_engine: str = "local"          # local | api
    stt_model: str = "NbAiLab/nb-whisper-small"
    cpu_threads: int = 8
    beam_size: int = 5
    api_model: str = "whisper-large-v3"
    language: str = "auto"             # auto | no | en | ...

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

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, data: dict) -> None:
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


settings = Settings()

# API-nokler leses kun fra miljo - aldri fra klienten
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
API_PROVIDER = os.getenv("API_PROVIDER", "groq")  # groq | openai
