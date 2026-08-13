# Commscribe

Sambandslogg med sanntids transkribering og oversettelse. Kobler radio eller
walkie-talkie til datamaskinen via aux, deler lyden i transmisjoner, transkriberer
hver enkelt og lagrer den med tidsstempel og avspilling.

## Slik virker det

Radio er PTT-basert, så kanalen er stille mellom transmisjoner. Backenden bruker
en RMS-terskel med pre-roll og hangover for å finne start og slutt på hver
transmisjon. Hvert segment skrives som WAV, legges i kø, transkriberes og
oversettes, og dyttes til nettleseren over WebSocket.

```
Radio → aux → USB-lydkort → sounddevice → segmentering → WAV
                                                          ↓
                              WebSocket ← SQLite ← oversettelse ← STT
```

## Kom i gang

```bash
cp .env.example .env      # valgfritt, kun for sky-API
./run.sh
```

Åpne http://127.0.0.1:8420

Første oppstart lager `.venv` og installerer avhengigheter.

### Lokal transkribering

```bash
.venv/bin/pip install faster-whisper
```

Standardmodell er `NbAiLab/nb-whisper-medium`, som er vesentlig bedre på norsk
enn OpenAI-vektene. Modellen lastes ned ved første bruk.

### Sky-API

Sett `GROQ_API_KEY` eller `OPENAI_API_KEY` i `.env` og velg *Sky-API* i UI-et.
Nøkler leses kun på server og eksponeres aldri mot klienten.

## Maskinvare

- Radioens høyttaler-/hodetelefonutgang → USB-lydkort med line-in
- Bruk dempeledd hvis signalet er for kraftig, og ground loop-isolator ved brumm
- Volumet på radioen bør stå slik at toppene ligger rundt −12 dBFS

## Innstillinger

| Felt | Beskrivelse |
|---|---|
| `threshold_db` | Nivå som regnes som tale. Senk hvis svake stasjoner mistes. |
| `min_duration` | Segmenter kortere enn dette kastes. Motvirker hallusinasjoner. |
| `hangover_ms` | Stillhet før segmentet lukkes. |
| `preroll_ms` | Lyd som tas med før terskelen brytes. |

## Struktur

```
backend/
  audio.py       lydfangst og segmentering
  storage.py     SQLite
  stt/           transkribering: local (faster-whisper) | api (Groq/OpenAI)
  translate/     oversettelse
  main.py        FastAPI, WebSocket, REST
web/             frontend
data/            opptak og database (gitignorert)
```

STT og oversettelse ligger bak hvert sitt grensesnitt, slik at motorer kan byttes
uten å røre resten — også når en mobilklient skal bruke samme API.

## Lisens

Privat prosjekt. Kontroller lokale regler for opptak av radiokommunikasjon før bruk.
