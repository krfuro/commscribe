"""Lokal transkribering med faster-whisper (stotter NB-Whisper)."""
from __future__ import annotations

import threading

from ..models import HUB_DIR
from .base import Transcript

_model = None
_model_key = None
_lock = threading.Lock()


def unload() -> None:
    """Slipp modellen fra minnet - brukes naar brukeren bytter modell."""
    global _model, _model_key
    with _lock:
        _model = None
        _model_key = None


def loaded_model() -> str | None:
    return _model_key[0] if _model_key else None


class LocalWhisper:
    name = "local"

    def __init__(self, model_id: str = "NbAiLab/nb-whisper-small",
                 compute_type: str = "int8", cpu_threads: int = 4,
                 beam_size: int = 5) -> None:
        self.model_id = model_id
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.beam_size = beam_size

    def _load(self):
        """Last modellen ved forste bruk - den er tung og skal deles."""
        global _model, _model_key
        key = (self.model_id, self.compute_type, self.cpu_threads)
        with _lock:
            if _model is None or _model_key != key:
                from faster_whisper import WhisperModel

                print(f"[stt] laster modell {self.model_id} ...")
                _model = WhisperModel(
                    self.model_id,
                    device="cpu",
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                    download_root=str(HUB_DIR),
                )
                _model_key = key
                print("[stt] modell klar")
        return _model

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        model = self._load()
        segments, info = model.transcribe(
            wav_path,
            language=None if language == "auto" else language,
            task=task,
            beam_size=self.beam_size,
            vad_filter=True,
            # Radiotrafikk henger ikke sammen fra transmisjon til transmisjon.
            # Uten dette drar Whisper forrige replikk med seg inn i neste.
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=[0.0, 0.2, 0.4],
        )
        parts = [s.text.strip() for s in segments]
        text = " ".join(p for p in parts if p).strip()
        return Transcript(text=text, language=info.language or language,
                          engine=f"{self.name}:{self.model_id.split('/')[-1]}",
                          confidence=getattr(info, "language_probability", None))
