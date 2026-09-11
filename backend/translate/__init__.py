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

PROVIDER_NAMES = {"groq": "Groq", "openai": "OpenAI", "ollama": "Ollama"}


def ollama_models(base_url: str, timeout: float = 5.0) -> list[str]:
    """Modellene en Ollama-server har lastet ned. Tom liste = ingen, eller nede."""
    resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
    resp.raise_for_status()
    return [m.get("name", "") for m in resp.json().get("models", []) if m.get("name")]


def resolve_ollama_model() -> str:
    """Modellen oversettelsen skal bruke: den valgte, ellers den forste som finnes.

    NOMAD-brukeren velger modell i NOMADs egne innstillinger, ikke hos oss, saa
    et tomt felt her betyr "bruk det som er der". Ingen modell er en feil med
    en forklaring, ikke en 404 fra Ollama som ser ut som et nettverksproblem.
    """
    if settings.ollama_model:
        return settings.ollama_model
    try:
        available = ollama_models(settings.ollama_url)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Naadde ikke Ollama paa {settings.ollama_url}: {exc}") from exc
    if not available:
        raise RuntimeError(
            "Ollama har ingen modeller. Last ned en (f.eks. llama3.2) i NOMAD "
            "under AI Assistant, eller med `ollama pull`."
        )
    return available[0]

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
        if self.provider not in PROVIDER_NAMES:
            self.provider = "groq"
        if self.provider == "ollama":
            self.model = model or ""       # loses opp ved bruk, se resolve_ollama_model
        else:
            self.model = model or DEFAULT_MODELS[self.provider]

    def _endpoint(self) -> tuple[str, dict, str]:
        """Adresse, hoder og modell for leverandoren. Ollama trenger ingen nokkel."""
        if self.provider == "ollama":
            return (f"{settings.ollama_url}/v1/chat/completions", {},
                    self.model or resolve_ollama_model())
        key = get_api_key(self.provider)
        if not key:
            raise RuntimeError(
                f"Mangler API-nokkel for {PROVIDER_NAMES[self.provider]}. "
                "Legg den inn under Innstillinger → Sky-API."
            )
        return CHAT_ENDPOINTS[self.provider], {"Authorization": f"Bearer {key}"}, self.model

    def translate(self, text: str, source: str, target: str) -> str:
        if not text.strip():
            return ""
        endpoint, headers, model = self._endpoint()

        target_name = LANG_NAMES.get(target, target)
        source_name = LANG_NAMES.get(source, source)
        system = (
            f"Du oversetter radiokommunikasjon fra {source_name} til {target_name}. "
            "Teksten er ofte kort, ufullstendig og inneholder fagsjargong. "
            "Svar KUN med oversettelsen - ingen forklaring, ingen anfoerselstegn. "
            "Behold tall, kallesignal og forkortelser uendret."
        )
        resp = httpx.post(
            endpoint,
            headers=headers,
            json={
                "model": model,
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


__all__ = ["Translator", "NoTranslator", "ApiTranslator", "get_translator", "LANG_NAMES",
           "PROVIDER_NAMES", "ollama_models", "resolve_ollama_model"]

