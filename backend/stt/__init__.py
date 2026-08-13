"""Fabrikk for transkriberingsmotorer."""
from __future__ import annotations

from ..config import settings
from .base import STTEngine, Transcript, is_hallucination


def get_engine(name: str, model: str) -> STTEngine:
    if name == "local":
        from .local import LocalWhisper

        return LocalWhisper(model_id=model, cpu_threads=settings.cpu_threads,
                            beam_size=settings.beam_size)
    if name == "api":
        from .api import ApiWhisper

        return ApiWhisper(model=model)
    raise ValueError(f"Ukjent STT-motor: {name}")


__all__ = ["STTEngine", "Transcript", "get_engine", "is_hallucination"]
