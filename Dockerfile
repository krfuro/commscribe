# syntax=docker/dockerfile:1
# Commscribe som container - for Project NOMAD og andre Docker-verter.
#
# Samme Python-tjeneste som skrivebordsappen pakker inn, uten Electron-skallet
# og uten lydinngang: en container har ingen lydenhet, saa lyd kommer inn som
# opplastede filer. Grensesnittet oppdager det selv (/api/config ->
# capabilities.capture = false) og legger seg om.
#
#   docker build -t commscribe .
#   docker run -p 8420:8420 -v commscribe:/data commscribe
#
# Se docs/NOMAD.md for oppsettet i NOMADs Supply Depot.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libgomp: OpenMP-kjoretiden ctranslate2 lener seg paa.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- modellen bakes inn ----------
# NOMAD er offline-forst. Installeres appen mens nettet er der og aapnes forst
# uten, skal den likevel virke - derfor ligger standardmodellen i bildet.
# Den ligger *ikke* i /data: NOMAD binder en vertsmappe dit, og en bind-mount
# faar ikke bildets innhold kopiert inn. backend/__main__.py kopierer fra
# denne mappa ved forste start (COMMSCRIBE_MODEL_SEED).
ARG SEED_MODEL=NbAiLab/nb-whisper-small
RUN python - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id=os.environ.get("SEED_MODEL") or "NbAiLab/nb-whisper-small",
    cache_dir="/opt/commscribe/models/hub",
    allow_patterns=["*.bin", "*.json", "*.txt", "*.model", "*.onnx"],
)
PY

COPY backend ./backend
COPY web ./web

# ---------- kjoring ----------
ENV COMMSCRIBE_CONTAINER=1 \
    COMMSCRIBE_DATA_DIR=/data \
    COMMSCRIBE_MODEL_SEED=/opt/commscribe/models \
    COMMSCRIBE_HOST=0.0.0.0 \
    COMMSCRIBE_PORT=8420 \
    # NOMAD har ingen innlogging, og "Open"-lenken kan ikke baere en nokkel.
    # Sett COMMSCRIBE_TOKEN og fjern denne for aa skru adgangskontrollen paa.
    COMMSCRIBE_NO_TOKEN=1 \
    # AI-assistentens Ollama paa NOMADs docker-nett. Overstyres i UI-et.
    COMMSCRIBE_OLLAMA_URL=http://nomad_ollama:11434 \
    # Hugging Face sporr etter nyere versjon ved lasting. Uten nett skal det
    # gi opp fort og bruke det som ligger lokalt, ikke vente ti sekunder.
    HF_HUB_ETAG_TIMEOUT=3 \
    HF_HUB_DISABLE_TELEMETRY=1

VOLUME ["/data"]
EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8420/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "backend"]
