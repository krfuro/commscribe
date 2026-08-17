"""Felles grensesnitt for transkriberingsmotorer."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Transcript:
    text: str
    language: str
    engine: str
    confidence: float | None = None


class STTEngine(Protocol):
    """Alle motorer implementerer dette. Bytt motor uten aa roere resten."""

    name: str

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        ...


# Whisper hallusinerer fast paa stille/stoyete klipp - modellen er trent paa
# undertekster, og faller tilbake paa rulleteksten naar den ikke horer tale.
HALLUCINATIONS = {
    "takk for at du så på",
    "takk for at du så på!",
    "takk for at du så",
    "undertekster av",
    "teksting av nicolai winther",
    "norsk tekst av",
    "tekst og teksting av",
    "thanks for watching",
    "thank you for watching",
    "subtitles by",
    "subtitled by",
    "amara.org",
    "please subscribe",
    "like and subscribe",
    "you",
    "bye",
    "so",
    "the",
    ".",
    "...",
}

_PUNCT = re.compile(r"^[\s.,!?\-–—_·]*$")


def is_hallucination(text: str) -> bool:
    clean = text.strip().lower()
    if not clean or _PUNCT.match(clean):
        return True
    if clean in HALLUCINATIONS:
        return True
    if any(clean.startswith(h) and len(clean) < len(h) + 15 for h in HALLUCINATIONS):
        return True
    # "takk takk takk takk ..." - modellen sitter fast i en lokke.
    words = clean.split()
    if len(words) >= 6 and len(set(words)) <= 2:
        return True
    return False
