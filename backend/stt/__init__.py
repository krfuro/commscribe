"""Fabrikk for transkriberingsmotorer."""
from __future__ import annotations

from ..config import settings
from .base import STTEngine, Transcript, is_hallucination


def get_engine(name: str, model: str) -> STTEngine:
    if name == "local":
        from .local import LocalWhisper

        return LocalWhisper(model_id=model, compute_type=settings.compute_type,
                            cpu_threads=settings.cpu_threads,
                            beam_size=settings.beam_size)
    if name == "api":
        from .api import ApiWhisper

        return ApiWhisper(model=model, provider=settings.api_provider)
    raise ValueError(f"Ukjent STT-motor: {name}")


def unload_local() -> None:
    """Slipp den lokale modellen. Trygt aa kalle selv om den aldri ble lastet."""
    try:
        from .local import unload

        unload()
    except ImportError:
        pass


__all__ = ["STTEngine", "Transcript", "get_engine", "is_hallucination", "unload_local"]
