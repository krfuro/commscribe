"""Lokal transkribering med faster-whisper (stotter NB-Whisper)."""
from __future__ import annotations

import threading

from .base import Transcript

_model = None
_model_id = None
_lock = threading.Lock()


class LocalWhisper:
    name = "local"

    def __init__(self, model_id: str = "NbAiLab/nb-whisper-medium",
                 compute_type: str = "int8") -> None:
        self.model_id = model_id
        self.compute_type = compute_type

    def _load(self):
        """Last modellen ved forste bruk - den er tung og skal deles."""
        global _model, _model_id
        with _lock:
            if _model is None or _model_id != self.model_id:
                from faster_whisper import WhisperModel

                print(f"[stt] laster modell {self.model_id} ...")
                _model = WhisperModel(self.model_id, device="cpu",
                                      compute_type=self.compute_type)
                _model_id = self.model_id
                print("[stt] modell klar")
        return _model

    def transcribe(self, wav_path: str, language: str = "auto",
                   task: str = "transcribe") -> Transcript:
        model = self._load()
        segments, info = model.transcribe(
            wav_path,
            language=None if language == "auto" else language,
            task=task,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return Transcript(text=text, language=info.language or language, engine=self.name)
