# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-oppskrift for Python-tjenesten.

Resultatet er en mappe med en kjorbar som skrivebordsskallet starter. Vi bygger
onedir og ikke onefile: onefile pakker ut hele biblioteket til en midlertidig
mappe ved hver start, og med ctranslate2 og modellkoden inne i bildet gir det
flere sekunders forsinkelse hver gang appen apnes.

    pyinstaller --noconfirm --clean packaging/commscribe-backend.spec
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent          # noqa: F821 - SPECPATH kommer fra PyInstaller

binaries = []
datas = [(str(ROOT / "web"), "web")]  # grensesnittet serveres av backenden
hiddenimports = []

# Pakker som tar med seg egne binaerfiler eller datafiler. Uten disse starter
# programmet, men faller om forste gang noen trykker Start.
for package in (
    "sounddevice",        # portaudio-biblioteket ligger i pakken
    "faster_whisper",     # VAD-modellen (silero) folger med som .onnx
    "ctranslate2",        # selve kjoremotoren for Whisper-vektene
    "av",                 # lyddekoding i faster-whisper
    "onnxruntime",
    "tokenizers",
    "huggingface_hub",
):
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    except Exception as exc:   # noqa: BLE001 - valgfrie pakker skal ikke stoppe bygget
        print(f"[spec] hopper over {package}: {exc}")
        continue
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# uvicorn og httpx laster protokolldelene sine dynamisk, saa statisk analyse
# finner dem ikke.
hiddenimports += collect_submodules("uvicorn")
hiddenimports += [
    # Opplasting: FastAPI importerer multipart-parseren forst naar en rute
    # med UploadFile tegnes, saa statisk analyse ser den ikke.
    "python_multipart", "multipart",
    "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.loops.asyncio",

    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan.on", "websockets.legacy", "websockets.legacy.server",
    "anyio._backends._asyncio", "h11", "httptools",
]

a = Analysis(                                   # noqa: F821
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Torch og de vitenskapelige pakkene drar inn hundrevis av megabyte som
    # aldri brukes - ctranslate2 er hele kjoremotoren vi trenger.
    excludes=[
        "torch", "torchaudio", "tensorflow", "matplotlib", "scipy", "pandas",
        "IPython", "jupyter", "notebook", "tkinter", "PyQt5", "PySide6", "PIL",
        "pytest", "setuptools._distutils",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)                               # noqa: F821

exe = EXE(                                      # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="commscribe-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # UPX gjor oppstarten tregere og skremmer antivirus
    # Konsollvindu paa Windows: skallet starter oss med CREATE_NO_WINDOW, saa
    # vinduet vises aldri, men stdout blir et ekte ror vi kan melde oss klar i.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(                                 # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="commscribe-backend",
)
