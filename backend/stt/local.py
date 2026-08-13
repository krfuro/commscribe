"""Lokal transkribering med faster-whisper (stotter NB-Whisper)."""
from __future__ import annotations

import threading

from .base import Transcript

_model = None
_model_key = None
_lock = threading.Lock()


class LocalWhisper:
    name = "local"

    def __init__(self, model_id: str = "NbAiLab/nb-whisper-small",
                 compute_type: str = "int8", cpu_threads: int = 8,
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
                _model = WhisperModel(self.model_id, device="cpu",
                                      compute_type=self.compute_type,
                                      cpu_threads=self.cpu_threads)
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
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return Transcript(text=text, language=info.language or language, engine=self.name)
