"""Opplastede lydfiler inn i loggen.

Radioen gir oss korte WAV-segmenter fra lydfangsten. En opplastet fil kan vaere
hva som helst - et timelangt mote i m4a, en mp3 fra en diktafon - og den
normaliseres derfor til det samme formatet (16 kHz, mono, 16-bit WAV) i det den
tas imot. Da er avspilling, sky-motoren, eksporten og oppryddingen noyaktig de
samme for begge kilder, og resten av appen trenger ikke vite hvor lyden kom fra.
Originalfilen beholdes ikke; navnet dens huskes paa raden.
"""
from __future__ import annotations

import datetime as dt
import re
import wave
from pathlib import Path

import numpy as np

from .audio import waveform_peaks, write_wav
from .config import REC_DIR, SAMPLE_RATE
from .i18n import t

# Filendelser vi tilbyr i filvelgeren. Dekodingen gaar via ffmpeg (pyav), saa
# lista er hva vi vil vise fram, ikke en teknisk grense.
ACCEPTED = (".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".flac", ".webm",
            ".mp4", ".wma", ".aiff", ".aif", ".caf", ".amr", ".3gp")

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _decode(path: Path) -> np.ndarray:
    """Les fila som float32-samples i 16 kHz mono."""
    try:
        from faster_whisper.audio import decode_audio

        return np.asarray(decode_audio(str(path), sampling_rate=SAMPLE_RATE),
                          dtype=np.float32)
    except ImportError:
        pass
    # Uten faster-whisper (pyav) klarer vi bare rene WAV-filer.
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError("Bare 16-bit WAV kan leses uten ffmpeg")
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        if wf.getnchannels() > 1:
            raw = raw.reshape(-1, wf.getnchannels()).mean(axis=1)
        samples = raw.astype(np.float32) / 32768.0
        rate = wf.getframerate()
    if rate != SAMPLE_RATE:
        # Enkel lineaer resampling. Godt nok for tale; ffmpeg-veien er bedre.
        n = int(len(samples) * SAMPLE_RATE / rate)
        samples = np.interp(np.linspace(0, len(samples) - 1, n),
                            np.arange(len(samples)), samples).astype(np.float32)
    return samples


def _peak_db(samples: np.ndarray) -> float:
    if samples.size == 0:
        return -120.0
    peak = float(np.max(np.abs(samples)))
    return 20.0 * np.log10(max(peak, 1e-9))


def parse_started_at(value: str | None) -> dt.datetime:
    """Tidspunktet klienten oppgir (filas endringstid), ellers naa.

    Loggen sorteres paa naar lyden ble tatt opp. Et mote fra i gaar som lastes
    opp i dag skal ligge under i gaar - ikke under opplastingstidspunktet.
    """
    if value:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone().replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
    return dt.datetime.now()


def ingest(src: Path, original_name: str, started_at: dt.datetime) -> dict:
    """Gjor en mottatt fil om til et segment paa disk.

    Returnerer feltene insert_segment trenger. Kaster ValueError hvis fila
    ikke lot seg dekode - kalleren svarer 400 med teksten.
    """
    try:
        samples = _decode(src)
    except Exception as exc:  # noqa: BLE001 - pyav kaster sine egne typer
        # ffmpeg navngir den midlertidige fila i meldingen; brukeren kjenner
        # bare sitt eget filnavn.
        reason = str(exc).replace(str(src), original_name)
        raise ValueError(t("upload_unreadable", name=original_name, reason=reason)) from exc

    if samples.size < SAMPLE_RATE // 10:
        raise ValueError(t("upload_silent"))

    day_dir = REC_DIR / started_at.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    stem = _SAFE.sub("_", Path(original_name).stem).strip("._")[:60] or "opplastet"
    path = day_dir / f"{started_at.strftime('%H%M%S')}_{stem}.wav"
    n = 1
    while path.exists():
        n += 1
        path = day_dir / f"{started_at.strftime('%H%M%S')}_{stem}-{n}.wav"
    write_wav(path, samples)

    return {
        "started_at": started_at.isoformat(timespec="seconds"),
        "duration": len(samples) / SAMPLE_RATE,
        "wav_path": str(path),
        "peak_db": _peak_db(samples),
        "waveform": waveform_peaks(samples),
        "origin": original_name[:200],
    }


__all__ = ["ACCEPTED", "ingest", "parse_started_at"]
