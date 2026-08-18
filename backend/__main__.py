"""Oppstart av Commscribe-serveren.

Kjores enten direkte (`python -m backend`) eller som pakket sidevogn under
skrivebordsappen. Skallet leser linja `COMMSCRIBE_READY {...}` fra stdout for aa
finne ut hvilken port serveren endte paa.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import sys
import threading
from datetime import datetime

import uvicorn

from . import main as backend_main
from .paths import LOG_DIR


class Tee:
    """Skriv til bade konsollen og loggfila.

    Naar appen er pakket har brukeren ingen terminal aa lese feilmeldinger i,
    men de trenger fortsatt aa havne et sted vi kan be om aa faa tilsendt.
    """

    def __init__(self, stream, path) -> None:
        self.stream = stream
        try:
            self.file = open(path, "a", encoding="utf-8", buffering=1)
        except OSError:
            self.file = None

    def write(self, data: str) -> int:
        if self.stream:
            try:
                self.stream.write(data)
            except Exception:  # noqa: BLE001
                pass
        if self.file:
            try:
                self.file.write(data)
            except Exception:  # noqa: BLE001
                pass
        return len(data)

    def flush(self) -> None:
        for target in (self.stream, self.file):
            try:
                if target:
                    target.flush()
            except Exception:  # noqa: BLE001
                pass

    def isatty(self) -> bool:
        return bool(self.stream and getattr(self.stream, "isatty", lambda: False)())


def _real_stream(stream, fd: int):
    """Hent tilbake stdout/stderr naar Python har mistet dem.

    En vindusbasert PyInstaller-bygging setter sys.__stdout__ til None fordi det
    ikke finnes noe konsollvindu. Roret fra skallet er der likevel, og det er
    nettopp der oppstartslinja maa ut - ellers venter skallet forgjeves.
    """
    if stream is not None:
        return stream
    try:
        return os.fdopen(fd, "w", encoding="utf-8", buffering=1, closefd=False)
    except OSError:
        return None


def setup_logging() -> None:
    log_path = LOG_DIR / f"commscribe-{datetime.now():%Y-%m-%d}.log"
    sys.stdout = Tee(_real_stream(sys.__stdout__, 1), log_path)
    sys.stderr = Tee(_real_stream(sys.__stderr__, 2), log_path)
    print(f"\n=== Commscribe startet {datetime.now():%Y-%m-%d %H:%M:%S} ===")
    _prune_logs()


def _prune_logs(keep: int = 14) -> None:
    """Ikke la loggmappa vokse i det uendelige."""
    try:
        logs = sorted(LOG_DIR.glob("commscribe-*.log"))
        for old in logs[:-keep]:
            old.unlink(missing_ok=True)
    except OSError:
        pass


def bind_socket(host: str, port: int) -> socket.socket:
    """Reserver porten selv.

    Med port 0 gir kjernen oss en ledig en, og fordi vi holder pa socketen kan
    ingen annen prosess ta den i mellomtiden. Aa lete etter en ledig port og
    deretter be uvicorn binde den ville vaert et kappløp vi kan tape.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    sock.set_inheritable(True)
    return sock


def selftest() -> int:
    """Sjekk at alt tungt lastet riktig i pakken.

    Naar en pakket app ikke virker, er det nesten alltid et bibliotek som ikke
    ble med. Da er dette det forste vi ber brukeren kjore - det skiller en
    odelagt pakke fra et oppsettsproblem paa maskinen.
    """
    from .paths import DATA_DIR, WEB_DIR, is_frozen

    ok = True
    print(f"Commscribe selvtest  (pakket: {'ja' if is_frozen() else 'nei'})")
    print(f"  data     : {DATA_DIR}")
    print(f"  web      : {WEB_DIR}  {'funnet' if WEB_DIR.is_dir() else 'MANGLER'}")
    ok &= WEB_DIR.is_dir()

    for label, probe in (
        ("numpy", lambda: __import__("numpy").__version__),
        ("sounddevice", lambda: __import__("sounddevice").get_portaudio_version()[1]),
        ("faster_whisper", lambda: __import__("faster_whisper").__version__),
        ("ctranslate2", lambda: __import__("ctranslate2").__version__),
        ("av", lambda: __import__("av").__version__),
        ("onnxruntime", lambda: __import__("onnxruntime").__version__),
        ("huggingface_hub", lambda: __import__("huggingface_hub").__version__),
        ("uvicorn", lambda: __import__("uvicorn").__version__),
    ):
        try:
            print(f"  {label:<16}: {probe()}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:<16}: FEIL - {exc}")
            ok &= label not in ("numpy", "faster_whisper", "ctranslate2", "uvicorn")

    try:
        from .audio import list_devices

        devices = list_devices()
        print(f"  lydenheter      : {len(devices['inputs'])} inn, "
              f"{len(devices['outputs'])} ut")
        if devices.get("error"):
            print(f"                    {devices['error']}")
    except Exception as exc:  # noqa: BLE001
        print(f"  lydenheter      : FEIL - {exc}")
        ok = False

    print("Selvtest: " + ("i orden" if ok else "noe mangler"))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="commscribe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0,
                        help="0 = velg en ledig port automatisk")
    parser.add_argument("--token", default="",
                        help="okt-nokkel; genereres hvis den utelates")
    parser.add_argument("--no-token", action="store_true",
                        help="skru av adgangskontroll (kun for utvikling)")
    parser.add_argument("--log", default="warning",
                        choices=["critical", "error", "warning", "info", "debug"])
    parser.add_argument("--selftest", action="store_true",
                        help="kontroller at pakken er komplett, og avslutt")
    parser.add_argument("--watch-stdin", action="store_true",
                        help="avslutt naar stdin lukkes (settes av skrivebordsskallet)")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    setup_logging()

    token = "" if args.no_token else (args.token or secrets.token_urlsafe(24))
    backend_main.configure(token)

    sock = bind_socket(args.host, args.port)
    host, port = sock.getsockname()[:2]

    # Skallet venter paa denne linja. Den maa ut for uvicorn tar over stdout.
    print("COMMSCRIBE_READY " + json.dumps(
        {"host": host, "port": port, "token": token,
         "url": f"http://{host}:{port}/" + (f"?token={token}" if token else "")}))
    sys.stdout.flush()

    config = uvicorn.Config(backend_main.app, log_level=args.log, access_log=False,
                            ws_ping_interval=20, ws_ping_timeout=20)
    server = uvicorn.Server(config)

    def shutdown(signum, frame) -> None:  # noqa: ARG001
        print("[commscribe] avslutter ...")
        server.should_exit = True

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, shutdown)
        except (ValueError, OSError):
            pass  # ikke hovedtraaden, eller ikke stottet paa plattformen

    if args.watch_stdin:
        # Skallet lukker roret naar det avslutter - ogsaa hvis det blir drept og
        # aldri far ryddet opp etter seg. Uten dette ville serveren blitt
        # liggende igjen med lydenheten opptatt og ingen maate aa stoppe den paa.
        # Bare paa forespoersel: kjort fra et skall der stdin alt er lukket, ville
        # den ellers avsluttet i samme oyeblikk som den startet.
        threading.Thread(target=_exit_when_stdin_closes, args=(server,),
                         daemon=True).start()

    server.run(sockets=[sock])
    return 0


def _exit_when_stdin_closes(server) -> None:
    stdin = sys.__stdin__
    if stdin is None:
        return
    try:
        stdin.read()
    except Exception:  # noqa: BLE001
        pass
    server.should_exit = True


if __name__ == "__main__":
    raise SystemExit(main())
