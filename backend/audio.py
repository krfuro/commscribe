"""Lydfangst fra radio + energibasert segmentering (squelch-deteksjon)."""
from __future__ import annotations

import datetime as dt
import queue
import threading
import wave
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd

from .config import CHANNELS, FRAME_SIZE, REC_DIR, SAMPLE_RATE, settings


def list_devices() -> dict:
    """Returner tilgjengelige inn- og utenheter."""
    devices = sd.query_devices()
    inputs, outputs = [], []
    for idx, dev in enumerate(devices):
        entry = {"index": idx, "name": dev["name"], "channels_in": dev["max_input_channels"],
                 "channels_out": dev["max_output_channels"]}
        if dev["max_input_channels"] > 0:
            inputs.append(entry)
        if dev["max_output_channels"] > 0:
            outputs.append(entry)
    try:
        default_in, default_out = sd.default.device
    except Exception:
        default_in = default_out = None
    return {"inputs": inputs, "outputs": outputs,
            "default_input": default_in, "default_output": default_out}


def rms_db(frame: np.ndarray) -> float:
    """Niva i dBFS for en ramme med float32-samples."""
    if frame.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(frame))))
    return 20.0 * np.log10(max(rms, 1e-9))


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())


class AudioCapture:
    """Fanger lyd, deler den i transmisjoner og skriver WAV per segment.

    Radio er PTT-basert: mellom transmisjoner er kanalen stille (squelch lukket).
    Vi bruker et RMS-terskel med pre-roll og hangover for aa finne grensene.
    """

    def __init__(self, on_segment) -> None:
        self.on_segment = on_segment          # callback(seg_id, wav_path, started_at, duration)
        self._stream: sd.InputStream | None = None
        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._running = threading.Event()
        self.level_db = -120.0                 # siste maalte niva, for VU-meter
        self.active = False                    # sender noen naa?

    # ---------- livssyklus ----------

    def start(self, device: int | None = None) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self._worker = threading.Thread(target=self._segmenter, daemon=True)
        self._worker.start()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=FRAME_SIZE,
            device=device if device is not None else settings.device,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        self._running.clear()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self.active = False
        self.level_db = -120.0

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    # ---------- intern ----------

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            print(f"[audio] {status}")
        self._queue.put(indata[:, 0].copy())

    def _segmenter(self) -> None:
        """Samler rammer til segmenter basert paa nivaaterskel."""
        preroll_frames = max(1, int(settings.preroll_ms / 30))
        preroll: deque = deque(maxlen=preroll_frames)
        buffer: list[np.ndarray] = []
        in_speech = False
        silence_ms = 0
        speech_frames = 0
        peak = -120.0
        started_at: dt.datetime | None = None

        while self._running.is_set():
            try:
                frame = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            level = rms_db(frame)
            self.level_db = level
            loud = level > settings.threshold_db

            if not in_speech:
                preroll.append(frame)
                if loud:
                    in_speech = True
                    self.active = True
                    started_at = dt.datetime.now()
                    buffer = list(preroll)
                    preroll.clear()
                    silence_ms = 0
                    speech_frames = 1
                    peak = level
                continue

            buffer.append(frame)
            peak = max(peak, level)
            if loud:
                silence_ms = 0
                speech_frames += 1
            else:
                silence_ms += 30
            duration = len(buffer) * 30 / 1000

            hit_hangover = silence_ms >= settings.hangover_ms
            hit_max = duration >= settings.max_duration
            if hit_hangover or hit_max:
                # Behold en kort hale, kast resten av hangover-stillheten.
                keep = max(0, (silence_ms - 200) // 30)
                trimmed = buffer[:-int(keep)] if keep else buffer
                self._flush(trimmed, started_at, peak, speech_frames)
                in_speech = False
                self.active = False
                buffer = []
                speech_frames = 0
                peak = -120.0

    def _flush(self, buffer: list[np.ndarray], started_at, peak: float,
               speech_frames: int) -> None:
        """Skriv segmentet til disk hvis det inneholder nok faktisk tale."""
        if not buffer or started_at is None:
            return
        # Maal TALEN, ikke bufferet: pre-roll og hangover er stillhet og skal
        # ikke telle med, ellers slipper korte blipp gjennom til Whisper.
        speech_duration = speech_frames * 30 / 1000
        if speech_duration < settings.min_duration:
            return
        samples = np.concatenate(buffer)
        duration = len(samples) / SAMPLE_RATE

        day_dir = REC_DIR / started_at.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / f"{started_at.strftime('%H%M%S_%f')[:-3]}.wav"
        write_wav(path, samples)

        try:
            self.on_segment(started_at.isoformat(timespec="seconds"), duration, str(path), peak)
        except Exception as exc:  # noqa: BLE001
            print(f"[audio] callback feilet: {exc}")
