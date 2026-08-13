"""Felles grensesnitt for transkriberingsmotorer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Transcript:
    text: str
    language: str
    engine: str


class STTEngine(Protocol):
    """Alle motorer implementerer dette. Bytt motor uten aa roere resten."""

    name: str

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        ...


# Whisper hallusinerer fast paa stille/stoyete klipp. Filtrer bort kjente frasar.
HALLUCINATIONS = {
    "takk for at du så på",
    "takk for at du så på!",
    "undertekster av",
    "teksting av nicolai winther",
    "norsk tekst av",
    "thanks for watching",
    "thanks for watching!",
    "thank you for watching",
    "subtitles by",
    "amara.org",
    "please subscribe",
    "you",
    ".",
}


def is_hallucination(text: str) -> bool:
    clean = text.strip().lower()
    if not clean:
        return True
    if clean in HALLUCINATIONS:
        return True
    return any(clean.startswith(h) and len(clean) < len(h) + 15 for h in HALLUCINATIONS)
