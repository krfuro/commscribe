# Commscribe

Radio log with real-time transcription and translation. Connect a radio or
walkie-talkie to the computer through the aux input, and Commscribe splits the
audio into transmissions, transcribes each one and stores it with a timestamp
and playback. Audio files can be uploaded too: meetings, dictations, recordings
from other devices.

Transcription runs locally with Whisper. The default model is NB-Whisper, trained
on Norwegian; OpenAI's multilingual weights are one click away. Nothing leaves
the building unless you deliberately turn on a cloud API.

Commscribe is produced by [Furo Engineering](https://furoengineering.com) and is
open source under the Apache License 2.0. Norsk utgave av denne sida:
[docs/README.no.md](docs/README.no.md).

## Download

Installers are built by CI and attached to every release:

| Platform | File | Installation |
|---|---|---|
| macOS (Apple Silicon / Intel) | `Commscribe-*-mac-*.dmg` | Open, drag Commscribe to Applications, start from Launchpad |
| Windows 10/11 | `Commscribe-*-win-x64.exe` | Run the installer; it adds a shortcut on the desktop and in Start |
| Linux | `.AppImage` / `.deb` | |
| Project NOMAD / Docker | `ghcr.io/krfuro/commscribe:<version>` | Supply Depot → *Add a custom app*, see [docs/NOMAD.md](docs/NOMAD.md) |

The container is the same service without audio input: audio is uploaded as
files and transcribed on the server. It is built to sit on a
[Project NOMAD](https://www.projectnomad.us/) next to NOMAD's own Ollama.

The app is not code-signed yet, so the first launch needs one extra click:

- **macOS**: right-click the app → *Open* → *Open anyway*
- **Windows**: *More info* → *Run anyway*

On first launch macOS asks for microphone access. Grant it; the audio input is
silent without it.

To build it yourself, see [docs/BUILD.md](docs/BUILD.md) (in Norwegian).

## How it works

Radio is push-to-talk, so the channel is silent between transmissions. The
backend uses an RMS threshold with pre-roll and hangover to find the start and
end of each transmission. Every segment is written as WAV, queued, transcribed
and translated, and pushed to the interface over WebSocket.

```
Radio → aux → USB sound card → sounddevice → segmentation → WAV
                                                            ↓
                          Electron window ← SQLite ← translation ← STT
```

The desktop app is an Electron shell around the same service. The shell starts
the Python service, which picks a free port and reports it back; the window
shows the interface the service serves. Everything is local: no accounts, no
cloud.

## Getting started

A three-step wizard asks for the language, the audio device and the speech
model. The model is downloaded once (Small is about 480 MB) and then used
without internet.

Then press **Start listening**. Every transmission appears as a card with time,
duration, waveform, playback and text.

| Shortcut | Action |
|---|---|
| `Space` | Start / stop listening |
| `/` or `Ctrl/⌘+F` | Search the log |
| `Ctrl/⌘+,` | Settings |
| Click the text | Correct the transcript |
| `Esc` | Close a panel, or stop playback |

## Uploading

**Upload** in the control bar, or dropping a file into the window, puts an
audio file into the same queue. Meetings, dictations and recordings from other
devices are transcribed like the radio, and the card carries the file name.
The file is converted to 16 kHz mono WAV on arrival so playback, export and
clean-up are the same for both sources; the original is not kept. The time on
the card is the file's modification time, so yesterday's meeting sorts under
yesterday.

Without an audio input (the container, or a machine without PortAudio) the
interface hides the listening controls and makes Upload the primary button.

## Languages

The interface is in English by default and can be switched to Norwegian,
Swedish, German, French or Spanish in the setup wizard or under Settings →
General. Each language is one file under `web/lang/`; a missing key falls back
to English, so a new translation can be added gradually. The desktop menu
follows the same setting.

The spoken language of the recordings is a separate setting under Settings →
Text.

## Hardware

- Radio speaker/headphone output → USB sound card with line-in
- Use an attenuator if the signal is too hot, and a ground-loop isolator on hum
- Set the radio's volume so peaks sit around −12 dBFS. The meter at the top
  shows the threshold as a dashed line and turns red on clipping.

## Settings

**Audio** — device, monitoring through the speaker, and detection:

| Field | Description |
|---|---|
| Threshold | Level that counts as speech. Lower it if weak stations are missed. |
| Shortest | Segments with less speech than this are discarded. Counters hallucinations. |
| Hangover | Silence before the segment is closed. |
| Pre-roll | Audio kept from before the threshold was crossed, so the first syllable is not cut off. |

**Text** — engine (local or cloud), spoken language, translation, and how many
CPU threads transcription may use.

**Models** — what is downloaded, how much space it takes, and downloads with
progress. `tiny` to `large`, plus OpenAI's weights for radio that is not
Norwegian.

**Cloud** — API key for Groq or OpenAI with a test button, or an Ollama on your
own machine or server. Keys are stored only on the machine, in a file only the
owner can read, and are never sent to the interface.

**General** — language, theme, autostart, how long recordings are kept, and a
shortcut to the data folder.

## Export

The log can be downloaded as `.txt`, `.md`, `.csv`, `.srt` or `.json`. The
search and filter you are in apply to the export, so you can pull out only the
starred cards, or only the hits on a call sign.

## Where things are stored

Recordings, database, settings and models live in the user's data folder, not
in the program, so they survive updates:

- macOS: `~/Library/Application Support/Commscribe/`
- Windows: `%APPDATA%\Commscribe\`
- Linux: `~/.local/share/commscribe/`
- Container: `/data` (on NOMAD: `/opt/project-nomad/storage/commscribe`)

Settings → General has a button that opens the folder.

## Translation

Whisper can translate to English by itself, offline and without a key. Other
target languages go through a language model: Groq or OpenAI with an API key,
or an **Ollama** on your own machine or on the server, without a key. Ollama is
chosen under Settings → Cloud; it does not transcribe audio, so the engine under
Text must then be Local.

## Layout

```
backend/
  paths.py       platform paths: program (read-only) vs. user data (writable)
  config.py      settings with persistence, model catalogue, API keys
  i18n.py        the few user-facing messages the service itself produces
  audio.py       capture, segmentation, monitoring, waveform
  upload.py      uploaded files into the queue, normalised to WAV
  storage.py     SQLite
  models.py      model downloads with progress
  export.py      txt / md / csv / srt / json
  stt/           transcription: local (faster-whisper) | api (Groq/OpenAI)
  translate/     translation
  main.py        FastAPI, WebSocket, REST
  __main__.py    startup, port selection, logging, self-test
web/             the interface (plain HTML/CSS/JS, no build step)
web/lang/        one JSON file per interface language
desktop/         the Electron shell and installer configuration
packaging/       PyInstaller spec, icon generator, smoke test
Dockerfile       the container image for Project NOMAD and other Docker hosts
docs/NOMAD.md    Supply Depot setup, and the entry proposed for NOMAD's catalogue
```

STT and translation sit behind their own interfaces so engines can be swapped
without touching the rest.

Most comments in the code are in Norwegian; that is the language the project
was written in, and translating them is ongoing.

## Security

The desktop service listens only on `127.0.0.1`, and every API call needs a
session token generated at each start and handed only to the app's own window.
Other programs and web pages on the machine get nowhere without it. The
container turns the token off, because NOMAD has no login of its own; see
[docs/NOMAD.md](docs/NOMAD.md).

## Licence

Apache License 2.0, see [LICENSE](LICENSE). Commscribe is produced by Furo
Engineering, and the [NOTICE](NOTICE) file carrying that attribution must be
kept in any redistribution. Check local rules on recording radio communication
before use.
