"""Sky-transkribering via Groq eller OpenAI (Whisper-kompatibelt endepunkt)."""
from __future__ import annotations

from pathlib import Path

import httpx

from ..config import get_api_key, settings
from .base import Transcript

ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/audio",
    "openai": "https://api.openai.com/v1/audio",
}

PROVIDER_NAMES = {"groq": "Groq", "openai": "OpenAI"}


class ApiWhisper:
    name = "api"

    def __init__(self, model: str = "whisper-large-v3", provider: str | None = None) -> None:
        self.model = model
        self.provider = provider or settings.api_provider
        # Ollama har ikke noe lydendepunkt. Sier vi ikke fra her, ville
        # valget stille blitt til Groq - og feilen ville sett ut som en
        # manglende nokkel.
        self.unsupported = self.provider == "ollama"
        if self.provider not in ENDPOINTS:
            self.provider = "groq"

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        if self.unsupported:
            raise RuntimeError(
                "Ollama kan ikke transkribere lyd. Velg lokal motor under Tekst, "
                "eller Groq/OpenAI under Sky."
            )
        key = get_api_key(self.provider)

        if not key:
            raise RuntimeError(
                f"Mangler API-nokkel for {PROVIDER_NAMES[self.provider]}. "
                "Legg den inn under Innstillinger → Sky-API."
            )
        kind = "translations" if task == "translate" else "transcriptions"
        endpoint = f"{ENDPOINTS[self.provider]}/{kind}"
        data = {"model": self.model, "response_format": "verbose_json"}
        if language != "auto" and task == "transcribe":
            data["language"] = language

        path = Path(wav_path)
        with path.open("rb") as fh:
            files = {"file": (path.name, fh, "audio/wav")}
            resp = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}"},
                data=data,
                files=files,
                timeout=90.0,
            )
        if resp.status_code == 401:
            raise RuntimeError(f"API-nokkelen for {PROVIDER_NAMES[self.provider]} ble avvist.")
        if resp.status_code == 429:
            raise RuntimeError(f"{PROVIDER_NAMES[self.provider]} har naadd kvotegrensa.")
        resp.raise_for_status()

        body = resp.json()
        return Transcript(
            text=(body.get("text") or "").strip(),
            language=body.get("language", language),
            engine=f"{self.name}:{self.provider}",
        )
