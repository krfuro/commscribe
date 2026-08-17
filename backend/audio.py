"""Lydfangst fra radio + energibasert segmentering (squelch-deteksjon)."""
from __future__ import annotations

import datetime as dt
import json
import queue
import threading
import wave
from collections import deque
from pathlib import Path

import numpy as np

from .config import CHANNELS, FRAME_MS, FRAME_SIZE, REC_DIR, SAMPLE_RATE, settings

# sounddevice krever PortAudio. Det folger med hjulene paa macOS og Windows, men
# mangler det likevel, skal appen starte og si fra - ikke doe ved import.
try:
    import sounddevice as sd

    AUDIO_ERROR: str | None = None
except (OSError, ImportError) as _exc:  # pragma: no cover - plattformavhengig
    sd = None
    AUDIO_ERROR = f"Lydsystemet er ikke tilgjengelig: {_exc}"
    print(f"[audio] {AUDIO_ERROR}")

WAVEFORM_BUCKETS = 48       # antall soyler i miniatyrbolgen UI-et tegner
MONITOR_MAX_LAG = 25        # rammer (~0,75 s) for vi begynner aa kaste medlytt


def list_devices() -> dict:
    """Returner tilgjengelige inn- og utenheter."""
    if sd is None:
        return {"inputs": [], "outputs": [], "default_input": None,
                "default_output": None, "error": AUDIO_ERROR}
    try:
        devices = sd.query_devices()
    except Exception as exc:  # noqa: BLE001
        # Ingen lydtjeneste tilgjengelig (kan skje pa en frisk maskin eller i CI).
        return {"inputs": [], "outputs": [], "default_input": None,
                "default_output": None, "error": str(exc)}

    inputs, outputs = [], []
    for idx, dev in enumerate(devices):
        entry = {"index": idx, "name": dev["name"],
                 "channels_in": dev["max_input_channels"],
                 "channels_out": dev["max_output_channels"],
                 "default_rate": int(dev.get("default_samplerate") or 0)}
        if dev["max_input_channels"] > 0:
            inputs.append(entry)
        if dev["max_output_channels"] > 0:
            outputs.append(entry)
    try:
        default_in, default_out = sd.default.device
    except Exception:  # noqa: BLE001
        default_in = default_out = None
    return {"inputs": inputs, "outputs": outputs,
            "default_input": default_in, "default_output": default_out}


def resolve_device(index: int | None, name: str = "") -> int | None:
    """Finn enheten paa nytt naar indeksene har flyttet seg.

    Lydenheter nummereres etter rekkefolgen de dukker opp i. Kobler brukeren fra
    et headset, glir alt etter det en plass ned, og en lagret indeks peker
    plutselig paa feil kort. Navnet er den stabile identiteten, saa vi lar det
    overstyre indeksen naar de er uenige.
    """
    devs = list_devices()["inputs"]
    if not devs:
        return index
    if name:
        for dev in devs:
            if dev["name"] == name:
                return dev["index"]
    if index is not None and any(d["index"] == index for d in devs):
        return index
    return devs[0]["index"] if devs else None


def rms_db(frame: np.ndarray) -> float:
    """Niva i dBFS for en ramme med float32-samples."""
    if frame.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(frame))))
    return 20.0 * np.log10(max(rms, 1e-9))


def waveform_peaks(samples: np.ndarray, buckets: int = WAVEFORM_BUCKETS) -> str:
    """Komprimer segmentet til noen faa toppverdier for miniatyrbolgen."""
    if samples.size == 0:
        return "[]"
    chunk = max(1, samples.size // buckets)
    usable = (samples.size // chunk) * chunk
    blocks = np.abs(samples[:usable]).reshape(-1, chunk).max(axis=1)
    if blocks.size == 0:
        return "[]"
    peak = float(blocks.max()) or 1.0
    scaled = np.clip(blocks / peak, 0.0, 1.0)
    return json.dumps([round(float(v), 3) for v in scaled[:buckets]])


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
    Vi bruker en RMS-terskel med pre-roll og hangover for aa finne grensene.
    """

    def __init__(self, on_segment, on_error=None) -> None:
        self.on_segment = on_segment
        self.on_error = on_error
        self._stream: sd.InputStream | None = None
        self._queue: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._running = threading.Event()

        self.level_db = -120.0                 # siste maalte niva, for VU-meter
        self.peak_db = -120.0                  # topphold, nullstilles av UI-et
        self.active = False                    # sender noen naa?
        self.clipping = False                  # signalet ligger paa taket
        self.last_error: str | None = None
        self.started_at: dt.datetime | None = None
        self.segments_seen = 0

        # Medlytt
        self._monitor_queue: queue.Queue = queue.Queue(maxsize=64)
        self._monitor_thread: threading.Thread | None = None
        self._monitor_running = threading.Event()
        self._monitor_device: int | None = None

    # ---------- livssyklus ----------

    def start(self, device: int | None = None) -> None:
        if self._running.is_set():
            return
        if sd is None:
            raise RuntimeError(AUDIO_ERROR or "Lydsystemet er ikke tilgjengelig")
        self.last_error = None
        device = resolve_device(
            device if device is not None else settings.device, settings.device_name)

        self._running.set()
        self._worker = threading.Thread(target=self._segmenter, daemon=True,
                                        name="commscribe-segmenter")
        self._worker.start()
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=FRAME_SIZE,
                device=device,
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            # Rydd opp saa en mislykket start ikke etterlater en levende traad.
            self._running.clear()
            self._stream = None
            raise

        self.started_at = dt.datetime.now()
        if settings.monitor_enabled and settings.monitor_device is not None:
            self._start_monitor(settings.monitor_device)

    def stop(self) -> None:
        self._running.clear()
        self._stop_monitor()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                print(f"[audio] feil ved lukking: {exc}")
            self._stream = None
        self.active = False
        self.level_db = -120.0
        self.peak_db = -120.0
        self.clipping = False
        self.started_at = None

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    def reset_peak(self) -> None:
        self.peak_db = -120.0

    # ---------- medlytt ----------

    def set_monitor(self, enabled: bool, device: int | None) -> None:
        """Slaa medlytt av eller paa, ogsaa midt i en okt."""
        if not enabled or device is None:
            self._stop_monitor()
            return
        if self._monitor_running.is_set() and device == self._monitor_device:
            return
        self._stop_monitor()
        if self.is_running:
            self._start_monitor(device)

    def _start_monitor(self, device: int) -> None:
        if self._monitor_running.is_set():
            return
        self._monitor_device = device
        self._monitor_running.set()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, args=(device,), daemon=True,
            name="commscribe-monitor")
        self._monitor_thread.start()

    def _stop_monitor(self) -> None:
        self._monitor_running.clear()
        self._monitor_device = None
        while not self._monitor_queue.empty():
            try:
                self._monitor_queue.get_nowait()
            except queue.Empty:
                break

    def _monitor_loop(self, device: int) -> None:
        """Spill lyden ut igjen paa hoyttaler/headset mens vi logger den.

        Egen strom framfor duplex: radioen kommer inn paa et USB-kort mens
        brukeren gjerne vil lytte paa noe helt annet, og en duplex-strom krever
        at inn og ut ligger paa samme enhet.
        """
        try:
            with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                                 dtype="float32", blocksize=FRAME_SIZE,
                                 device=device) as out:
                while self._monitor_running.is_set():
                    try:
                        frame = self._monitor_queue.get(timeout=0.3)
                    except queue.Empty:
                        continue
                    gain = settings.monitor_gain
                    if gain != 1.0:
                        frame = np.clip(frame * gain, -1.0, 1.0)
                    out.write(frame.reshape(-1, 1))
        except Exception as exc:  # noqa: BLE001
            # Medlytt er en bekvemmelighet. Feiler den, skal loggingen fortsette.
            print(f"[audio] medlytt stoppet: {exc}")
            self._monitor_running.clear()
            if self.on_error:
                self.on_error(f"Medlytt utilgjengelig: {exc}", fatal=False)

    # ---------- intern ----------

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            # Overflow betyr at vi ikke rakk aa tomme bufferet. Verdt aa logge,
            # men ikke noe aa stoppe for - rammen er fortsatt gyldig.
            print(f"[audio] {status}")
        frame = indata[:, 0].copy()
        self._queue.put(frame)
        if self._monitor_running.is_set():
            try:
                self._monitor_queue.put_nowait(frame)
            except queue.Full:
                pass  # heller hakkete medlytt enn etterslep i loggen

    def _segmenter(self) -> None:
        """Samler rammer til segmenter basert paa nivaaterskel."""
        preroll: deque = deque(maxlen=max(1, int(settings.preroll_ms / FRAME_MS)))
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

            # Les innstillingene per ramme - brukeren justerer terskelen mens
            # det gaar, og skal se effekten med en gang.
            want_preroll = max(1, int(settings.preroll_ms / FRAME_MS))
            if preroll.maxlen != want_preroll:
                preroll = deque(preroll, maxlen=want_preroll)

            level = rms_db(frame)
            self.level_db = level
            self.peak_db = max(self.peak_db, level)
            self.clipping = bool(np.max(np.abs(frame)) >= 0.99)
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
                silence_ms += FRAME_MS
            duration = len(buffer) * FRAME_MS / 1000

            hit_hangover = silence_ms >= settings.hangover_ms
            hit_max = duration >= settings.max_duration
            if hit_hangover or hit_max:
                # Behold en kort hale, kast resten av hangover-stillheten.
                keep = max(0, (silence_ms - 200) // FRAME_MS)
                trimmed = buffer[:-int(keep)] if keep else buffer
                self._flush(trimmed, started_at, peak, speech_frames)
                in_speech = False
                self.active = False
                buffer = []
                speech_frames = 0
                peak = -120.0

        # Stoppet midt i en transmisjon: ta vare paa det vi har.
        if in_speech and buffer:
            self._flush(buffer, started_at, peak, speech_frames)
            self.active = False

    def _flush(self, buffer: list[np.ndarray], started_at, peak: float,
               speech_frames: int) -> None:
        """Skriv segmentet til disk hvis det inneholder nok faktisk tale."""
        if not buffer or started_at is None:
            return
        # Maal TALEN, ikke bufferet: pre-roll og hangover er stillhet og skal
        # ikke telle med, ellers slipper korte blipp gjennom til Whisper.
        speech_duration = speech_frames * FRAME_MS / 1000
        if speech_duration < settings.min_duration:
            return

        samples = np.concatenate(buffer)
        duration = len(samples) / SAMPLE_RATE

        day_dir = REC_DIR / started_at.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / f"{started_at.strftime('%H%M%S_%f')[:-3]}.wav"
        try:
            write_wav(path, samples)
        except OSError as exc:
            print(f"[audio] kunne ikke skrive {path}: {exc}")
            if self.on_error:
                self.on_error(f"Kunne ikke lagre opptak: {exc}", fatal=False)
            return

        self.segments_seen += 1
        try:
            self.on_segment(started_at.isoformat(timespec="seconds"), duration,
                            str(path), peak, waveform_peaks(samples))
        except Exception as exc:  # noqa: BLE001
            print(f"[audio] callback feilet: {exc}")
