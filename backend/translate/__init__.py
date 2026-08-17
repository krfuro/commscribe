"""Oversettelse. Whisper kan kun oversette TIL engelsk - derfor eget ledd."""
from __future__ import annotations

from typing import Protocol

import httpx

from ..config import get_api_key, settings

CHAT_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}

DEFAULT_MODELS = {"groq": "llama-3.3-70b-versatile", "openai": "gpt-4o-mini"}

LANG_NAMES = {
    "no": "norsk", "nb": "norsk bokmal", "nn": "nynorsk", "en": "engelsk",
    "sv": "svensk", "da": "dansk", "fi": "finsk", "is": "islandsk",
    "de": "tysk", "nl": "nederlandsk", "fr": "fransk", "es": "spansk",
    "it": "italiensk", "pt": "portugisisk", "pl": "polsk", "ru": "russisk",
    "uk": "ukrainsk", "ar": "arabisk", "tr": "tyrkisk", "so": "somali",
}


class Translator(Protocol):
    name: str

    def translate(self, text: str, source: str, target: str) -> str:
        ...


class NoTranslator:
    name = "none"

    def translate(self, text: str, source: str, target: str) -> str:  # noqa: ARG002
        return ""


class ApiTranslator:
    name = "api"

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = provider or settings.api_provider
        if self.provider not in DEFAULT_MODELS:
            self.provider = "groq"
        self.model = model or DEFAULT_MODELS[self.provider]

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return ""
        key = get_api_key(self.provider)
        if not key:
            raise RuntimeError(
                f"Mangler API-nokkel for {self.provider}. "
                "Legg den inn under Innstillinger → Sky-API."
            )

        target_name = LANG_NAMES.get(target, target)
        source_name = LANG_NAMES.get(source, source)
        system = (
            f"Du oversetter radiokommunikasjon fra {source_name} til {target_name}. "
            "Teksten er ofte kort, ufullstendig og inneholder fagsjargong. "
            "Svar KUN med oversettelsen - ingen forklaring, ingen anfoerselstegn. "
            "Behold tall, kallesignal og forkortelser uendret."
        )
        resp = httpx.post(
            CHAT_ENDPOINTS[self.provider],
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": self.model,
                "temperature": 0.1,
                "max_tokens": 500,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def get_translator(name: str) -> Translator:
    if name in ("none", "", None):
        return NoTranslator()
    if name == "api":
        return ApiTranslator()
    raise ValueError(f"Ukjent oversetter: {name}")


__all__ = ["Translator", "NoTranslator", "ApiTranslator", "get_translator", "LANG_NAMES"]
