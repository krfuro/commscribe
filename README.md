# Commscribe

Sambandslogg med sanntids transkribering og oversettelse. Kobler radio eller
walkie-talkie til datamaskinen via aux, deler lyden i transmisjoner, transkriberer
hver enkelt og lagrer den med tidsstempel og avspilling.

Transkriberingen skjer lokalt på maskinen med NB-Whisper, som er trent på norsk.
Ingenting sendes ut av huset med mindre du selv slår på sky-API.

## Last ned

Ferdige installasjonsfiler bygges av CI og legges ved hver utgivelse:

| Plattform | Fil | Installasjon |
|---|---|---|
| macOS (Apple Silicon / Intel) | `Commscribe-*-mac-*.dmg` | Åpne, dra Commscribe til Programmer, start fra Launchpad |
| Windows 10/11 | `Commscribe-*-win-x64.exe` | Kjør installasjonsfila — legger igjen snarvei på skrivebordet og i Start |
| Linux | `.AppImage` / `.deb` | |
| Project NOMAD / Docker | `ghcr.io/krfuro/commscribe:<versjon>` | Supply Depot → *Add a custom app*, se [docs/NOMAD.md](docs/NOMAD.md) |

Containeren er den samme tjenesten uten lydinngang: lyd lastes opp som filer og
transkriberes på serveren. Den er laget for å ligge på en
[Project NOMAD](https://www.projectnomad.us/) ved siden av NOMADs egen Ollama.

Appen er foreløpig ikke signert, så første gang må du klikke bort en advarsel:

- **macOS**: høyreklikk appen → *Åpne* → *Åpne likevel*
- **Windows**: *Mer informasjon* → *Kjør likevel*

Første gang du starter appen ber macOS om mikrofontilgang. Den må du gi —
lydinngangen er stille uten.

Skal du bygge selv, se [docs/BUILD.md](docs/BUILD.md).

## Slik virker det

Radio er PTT-basert, så kanalen er stille mellom transmisjoner. Backenden bruker
en RMS-terskel med pre-roll og hangover for å finne start og slutt på hver
transmisjon. Hvert segment skrives som WAV, legges i kø, transkriberes og
oversettes, og dyttes til grensesnittet over WebSocket.

```
Radio → aux → USB-lydkort → sounddevice → segmentering → WAV
                                                          ↓
                        Electron-vindu ← SQLite ← oversettelse ← STT
```

Skrivebordsappen er et Electron-skall rundt den samme tjenesten. Skallet starter
Python-tjenesten, som velger en ledig port og melder den tilbake; vinduet viser
grensesnittet tjenesten serverer. Alt lokalt, ingen kontoer, ingen sky.

## Første oppstart

En veiviser i tre steg spør om lydenhet og språkmodell. Modellen lastes ned én
gang (small er ca. 480 MB) og brukes deretter uten nett.

Etterpå: trykk **Start lytting**. Hver transmisjon dukker opp som et kort med
klokkeslett, varighet, bølgeform, avspilling og tekst.

## Opplasting

**Last opp** i kontrollraden — eller slipp en fil i vinduet — legger en
lydfil i den samme køen. Møter, diktater og opptak fra andre enheter
transkriberes på samme måte som radioen, og kortet får filnavnet som merke.
Fila gjøres om til 16 kHz mono WAV ved mottak, så avspilling, eksport og
opprydding er de samme for begge kilder; originalen beholdes ikke. Tidspunktet
er filas endringstid, slik at et møte fra i går sorteres under i går.

Uten lydinngang (containeren, eller en maskin uten PortAudio) skjuler
grensesnittet lyttingen og gjør opplasting til hovedknappen.

| Snarvei | Handling |
|---|---|
| `Mellomrom` | Start / stopp lyttingen |
| `/` eller `Ctrl/⌘+F` | Søk i loggen |
| `Ctrl/⌘+,` | Innstillinger |
| Klikk på teksten | Rett transkripsjonen |
| `Esc` | Lukk panel, eller stopp avspilling |

## Maskinvare

- Radioens høyttaler-/hodetelefonutgang → USB-lydkort med line-in
- Bruk dempeledd hvis signalet er for kraftig, og ground loop-isolator ved brumm
- Volumet på radioen bør stå slik at toppene ligger rundt −12 dBFS. Nivåmåleren
  i toppen viser terskelen som en stiplet strek, og lyser rødt ved klipping.

## Innstillinger

**Lyd** — lydenhet, medlytt i høyttaleren, og deteksjonen:

| Felt | Beskrivelse |
|---|---|
| Terskel | Nivå som regnes som tale. Senk hvis svake stasjoner mistes. |
| Korteste | Segmenter med mindre tale enn dette kastes. Motvirker hallusinasjoner. |
| Hangover | Stillhet før segmentet lukkes. |
| Pre-roll | Lyd som tas med før terskelen brytes, så første stavelse ikke kappes. |

**Tekst** — motor (lokal eller sky), talespråk, oversettelse, og hvor mange
CPU-tråder transkriberingen får bruke.

**Modeller** — hva som er lastet ned, hvor mye plass det tar, og nedlasting med
framdrift. `tiny` til `large`, i tillegg til OpenAI-vektene for samband som ikke
er norsk.

**Sky** — API-nøkkel for Groq eller OpenAI, med en testknapp. Nøkkelen lagres
bare på maskinen, i en fil som kun eieren kan lese, og sendes aldri til
grensesnittet.

**Om** — drakt, autostart, hvor lenge opptak beholdes, og en snarvei til
datamappa.

## Eksport

Loggen kan lastes ned som `.txt`, `.md`, `.csv`, `.srt` eller `.json`. Søket og
filteret du står i gjelder for eksporten, så du kan hente ut bare det som er
stjernemerket, eller bare treff på et kallesignal.

## Hvor ting lagres

Opptak, database, innstillinger og modeller ligger i brukerens datamappe, ikke i
programmet — de overlever oppdateringer:

- macOS: `~/Library/Application Support/Commscribe/`
- Windows: `%APPDATA%\Commscribe\`
- Linux: `~/.local/share/commscribe/`

Under *Innstillinger → Om* er det en knapp som åpner mappa.

## Oversettelse

Whisper kan oversette til engelsk selv, uten nett og uten nøkkel. Andre målspråk
går gjennom en språkmodell: Groq eller OpenAI med API-nøkkel, eller en
**Ollama** på egen maskin eller på serveren, uten nøkkel. Ollama velges under
Innstillinger → Sky; den transkriberer ikke lyd, så motoren under Tekst må da
stå på Lokal.


## Struktur

```
backend/
  paths.py       plattformstier: program (lesing) vs. brukerdata (skriving)
  config.py      innstillinger med lagring, modellkatalog, API-nøkler
  audio.py       lydfangst, segmentering, medlytt, bølgeform
  storage.py     SQLite
  models.py      nedlasting av modeller med framdrift
  export.py      txt / md / csv / srt / json
  upload.py      opplastede filer inn i koen, normalisert til WAV
  stt/           transkribering: local (faster-whisper) | api (Groq/OpenAI)
  translate/     oversettelse
  main.py        FastAPI, WebSocket, REST
  __main__.py    oppstart, portvalg, logg, selvtest
web/             grensesnittet (vanlig HTML/CSS/JS, ingen byggesteg)
desktop/         Electron-skallet og oppsett for installasjonsfiler
packaging/       PyInstaller-oppskrift, ikongenerator, røykprøve
Dockerfile       containerbildet for Project NOMAD og andre Docker-verter
docs/NOMAD.md    oppsett i Supply Depot, og oppføringen til NOMADs katalog
```

STT og oversettelse ligger bak hvert sitt grensesnitt, slik at motorer kan byttes
uten å røre resten — også når en mobilklient skal bruke samme API.

## Sikkerhet

Tjenesten lytter bare på `127.0.0.1`, og alle API-kall krever en økt-nøkkel som
lages på nytt ved hver oppstart og bare gis til appens eget vindu. Uten den
kommer andre programmer og nettsider på maskinen ingen vei.

## Lisens

Privat prosjekt. Kontroller lokale regler for opptak av radiokommunikasjon før bruk.
