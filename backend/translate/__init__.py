"""Oversettelse. Whisper kan kun oversette TIL engelsk - derfor eget ledd."""
from __future__ import annotations

from typing import Protocol

import httpx

from ..config import API_PROVIDER, GROQ_API_KEY, OPENAI_API_KEY

CHAT_ENDPOINTS = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}

DEFAULT_MODELS = {"groq": "llama-3.3-70b-versatile", "openai": "gpt-4o-mini"}

LANG_NAMES = {
    "no": "norsk", "nb": "norsk bokmal", "en": "engelsk", "sv": "svensk",
    "da": "dansk", "fi": "finsk", "de": "tysk", "fr": "fransk",
    "es": "spansk", "ru": "russisk", "pl": "polsk", "uk": "ukrainsk",
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
        self.provider = provider or API_PROVIDER
        self.model = model or DEFAULT_MODELS[self.provider]
        self.key = GROQ_API_KEY if self.provider == "groq" else OPENAI_API_KEY

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return ""
        if not self.key:
            raise RuntimeError(f"Mangler API-nokkel for {self.provider}. Sett den i .env")

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
            headers={"Authorization": f"Bearer {self.key}"},
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
