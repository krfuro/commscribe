#!/usr/bin/env python3
"""Roykprove for den pakkede tjenesten.

PyInstaller feiler stille: bygget gaar fint, men programmet doer ved oppstart
fordi en modul ikke ble med. Her starter vi den faktiske kjorbaren, venter paa
oppstartslinja og sporr et par endepunkter, slik at et odelagt bygg stopper i
CI framfor aa bli lastet ned av noen.

    python packaging/verify_backend.py [sti/til/mappe]
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIST = ROOT / "desktop" / "resources" / "backend-dist" / "commscribe-backend"
READY_PREFIX = "COMMSCRIBE_READY "
TIMEOUT = 120


def find_binary(dist: Path) -> Path:
    exe = dist / ("commscribe-backend.exe" if sys.platform == "win32"
                  else "commscribe-backend")
    if not exe.exists():
        raise SystemExit(f"FEIL: fant ikke {exe}")
    return exe


def get(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"X-Commscribe-Token": token})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main() -> int:
    dist = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIST
    exe = find_binary(dist)

    # Selvtesten sier hvilket bibliotek som mangler. Uten den ville et ufullstendig
    # bygg bare gitt "tjenesten meldte seg aldri klar".
    print("--- selvtest ---")
    check = subprocess.run([str(exe), "--selftest"], text=True, timeout=180)
    if check.returncode != 0:
        raise SystemExit("FEIL: selvtesten fant mangler i pakken")

    print(f"--- oppstart ---\nstarter {exe}")

    proc = subprocess.Popen(
        [str(exe), "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )

    info = None
    deadline = time.time() + TIMEOUT
    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    raise SystemExit(f"FEIL: tjenesten avsluttet med kode {proc.returncode}")
                continue
            print(f"  | {line.rstrip()}")
            if line.startswith(READY_PREFIX):
                info = json.loads(line[len(READY_PREFIX):])
                break
        if info is None:
            raise SystemExit("FEIL: tjenesten meldte seg aldri klar")

        base = f"http://{info['host']}:{info['port']}"
        token = info["token"]

        health = get(f"{base}/health", token)
        assert health.get("ok"), health
        print(f"  health: {health}")

        status = get(f"{base}/api/status", token)
        print(f"  status: kø={status['queue']} motor={status['engine']}")

        # Enhetslista gaar gjennom PortAudio. Byggeserveren har ingen lydkort,
        # saa en tom liste er greit - poenget er at biblioteket ble med.
        devices = get(f"{base}/api/devices", token)
        print(f"  lydenheter: {len(devices['inputs'])} inn, "
              f"{len(devices['outputs'])} ut"
              + (f" ({devices['error']})" if devices.get("error") else ""))

        models = get(f"{base}/api/models", token)
        assert models["models"], "modellkatalogen er tom"
        print(f"  modeller: {len(models['models'])} i katalogen")

        # Uten nokkel skal ingenting slippe gjennom.
        try:
            urllib.request.urlopen(f"{base}/api/status", timeout=10)
            raise SystemExit("FEIL: API-et svarte uten okt-nokkel")
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise SystemExit(f"FEIL: forventet 401, fikk {exc.code}") from exc

        # Grensesnittet maa ha blitt med i pakken.
        with urllib.request.urlopen(f"{base}/", timeout=15) as resp:
            body = resp.read().decode("utf-8", "replace")
        assert "Commscribe" in body, "web-grensesnittet mangler i pakken"
        print("  grensesnitt: ok")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("Tjenesten er i orden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
