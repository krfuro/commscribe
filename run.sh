#!/usr/bin/env bash
# Start Commscribe uten skrivebordsskallet - nyttig under utvikling og hvis du
# heller vil kjore alt i nettleseren. Skrivebordsappen bygges med
# desktop/-oppsettet, se docs/BUILD.md.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Oppretter virtuelt miljø ..."
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi

# Fast port og ingen okt-nokkel, sa adressen under kan apnes direkte.
echo "Åpne http://127.0.0.1:8420"
exec .venv/bin/python -m backend --port 8420 --no-token "$@"
