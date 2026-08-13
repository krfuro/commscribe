"""Sky-transkribering via Groq eller OpenAI (Whisper-kompatibelt endepunkt)."""
from __future__ import annotations

from pathlib import Path

import httpx

from ..config import API_PROVIDER, GROQ_API_KEY, OPENAI_API_KEY
from .base import Transcript

ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/audio",
    "openai": "https://api.openai.com/v1/audio",
}


class ApiWhisper:
    name = "api"

    def __init__(self, model: str = "whisper-large-v3", provider: str | None = None) -> None:
        self.model = model
        self.provider = provider or API_PROVIDER
        self.key = GROQ_API_KEY if self.provider == "groq" else OPENAI_API_KEY

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        if not self.key:
            raise RuntimeError(
                f"Mangler API-nokkel for {self.provider}. Sett den i .env"
            )
        endpoint = f"{ENDPOINTS[self.provider]}/{'translations' if task == 'translate' else 'transcriptions'}"
        data = {"model": self.model, "response_format": "verbose_json"}
        if language != "auto" and task == "transcribe":
            data["language"] = language

        path = Path(wav_path)
        with path.open("rb") as fh:
            files = {"file": (path.name, fh, "audio/wav")}
            resp = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.key}"},
                data=data,
                files=files,
                timeout=90.0,
            )
        resp.raise_for_status()
        body = resp.json()
        return Transcript(
            text=(body.get("text") or "").strip(),
            language=body.get("language", language),
            engine=f"{self.name}:{self.provider}",
        )
