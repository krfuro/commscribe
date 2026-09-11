# Commscribe på Project NOMAD

[Project NOMAD](https://www.projectnomad.us/) er en offline kunnskapsserver:
Wikipedia, kart, kurs og en lokal språkmodell (Ollama) i Docker-containere på
en maskin du eier, styrt fra et kommandosenter på port 8080. Commscribe finnes
som et containerbilde laget for nettopp den serveren: lydfiler lastes opp i
nettleseren, transkriberes på NOMAD-maskinen med NB-Whisper, og oversettes av
NOMADs egen Ollama. Ingenting forlater huset.

Det er den samme Python-tjenesten som skrivebordsappen pakker inn. Forskjellen
er hva som er rundt den:

| | Skrivebordsappen | Containeren |
|---|---|---|
| Lyd inn | Radio via lydkort, i sanntid | Opplastede filer |
| Kjører på | Din egen Mac/PC | NOMAD-serveren (eller en annen Docker-vert) |
| Åpnes | Som et program | I nettleseren, fra NOMADs forside |
| Innlogging | Øktnøkkel, bare appens eget vindu | Ingen, som resten av NOMAD |
| Oversettelse | Groq/OpenAI (nøkkel) eller Ollama | NOMADs Ollama, uten nøkkel |

## Installere i Supply Depot

Fram til Commscribe ligger i NOMADs egen katalog legges den inn som en
**egendefinert app**. Åpne NOMAD → **Supply Depot** → **Add a custom app** og
fyll inn:

| Felt | Verdi |
|---|---|
| Name | `Commscribe` |
| Image | `ghcr.io/krfuro/commscribe:1.1.0` |
| Icon | `IconMicrophone` (valgfritt) |
| Port mapping | container `8420` → host `8460` |
| Volume bind | `/opt/project-nomad/storage/commscribe` → `/data` |
| Memory limit | 2048 MB (modellen bruker rundt en gigabyte under transkribering) |
| CPUs | 2 eller flere — transkriberingen skalerer med kjerner |

Bruk alltid et fullt versjonsnummer i bildenavnet. NOMAD advarer mot `:latest`
fordi den ikke kan versjonsspore det, og advarselen er berettiget.

Trykk **Install**. NOMAD henter bildet (rundt en gigabyte — standardmodellen
ligger inni), starter containeren, og Commscribe får et kort på forsiden med
en **Open**-knapp som går til `http://<nomad>:8460`.

Ingen miljøvariabler trengs. Bildet setter selv det som skal til for NOMAD:
lytting på alle grensesnitt, port 8420 innvendig, adgangskontroll av, og
Ollama-adressen `http://nomad_ollama:11434`, som er navnet AI-assistentens
container har på NOMADs docker-nett.

### Etter installasjon

1. **Veiviseren** åpner første gang. Den vet at det ikke finnes noen
   lydinngang, og hopper rett til språkmodellen. `nb-whisper-small` er
   allerede på plass; de større kan lastes ned der mens nettet er tilgjengelig.
2. **Last opp** en lydfil, eller slipp den i vinduet. Fila legges i køen,
   transkriberes og dukker opp som et kort — med avspilling, tekst og eksport
   som ellers. Tidspunktet på kortet er filas endringstid, så et møte fra i
   går havner under i går.
3. **Oversettelse** slås på under Innstillinger → Tekst (Modus: oversett).
   Engelsk gjør Whisper selv. Andre språk går gjennom Ollama, forutsatt at
   AI-assistenten er installert i NOMAD og har minst én modell lastet ned.
   Innstillinger → Sky → **Test tilkoblingen** sier om Commscribe når den.

## Hva som lagres, og hvor

Alt Commscribe skriver ligger under `/opt/project-nomad/storage/commscribe`
på verten (`/data` inne i containeren): databasen, WAV-filene, innstillingene
og modellene. Mappa overlever oppdateringer og fjerning av appen, på samme
måte som for NOMADs egne apper. Opplastede filer gjøres om til 16 kHz mono
WAV ved mottak — rundt 115 MB per time — og originalen beholdes ikke.

## Verdt å vite

- **Ingen innlogging.** NOMAD har ingen, og Open-lenken kan ikke bære en
  nøkkel, så bildet skrur adgangskontrollen av. Alle som når port 8460 kan
  lese og slette loggen — det er samme grense som Stirling PDF og File
  Browser lever med. NOMAD-utviklerne fraråder å eksponere serveren mot
  internett, og det gjelder her også. Vil du ha en nøkkel likevel: sett
  `COMMSCRIBE_TOKEN` til noe hemmelig og fjern `COMMSCRIBE_NO_TOKEN` i appens
  miljøvariabler, og legg `?token=<nøkkelen>` på en egendefinert Open-lenke
  (Manage → Edit → Custom URL).
- **Ingen radio i containeren.** Supply Depot gir ikke containere tilgang
  til lydenheter, så en walkie-talkie på aux må gå gjennom skrivebordsappen
  på maskinen lydkortet står i. Å la skrivebordsappen sende segmentene sine
  til Commscribe på NOMAD er neste steg, og er ikke laget ennå.
- **Ingen mikrofon i nettleseren ennå.** Nettlesere tillater bare opptak fra
  en sikker side (HTTPS), og NOMAD-apper serveres over HTTP. NOMAD har et
  mønster for dette (MeshCore Web og Vaultwarden kjører HTTPS med selvsignert
  sertifikat, portbindingen `https:<port>`); det er veien når opptak i
  nettleseren skal inn.
- **Sky-motorene virker fortsatt**, hvis serveren har nett og du legger inn
  en nøkkel. Men Ollama transkriberer ikke lyd — velger du den som
  leverandør, må motoren under Tekst stå på Lokal.

## Bygge bildet selv

```bash
docker build -t commscribe .
docker run --rm -p 8420:8420 -v commscribe:/data commscribe
```

`Dockerfile` baker `NbAiLab/nb-whisper-small` inn under `/opt/commscribe/models`
og kopierer den inn i `/data/models` første gang containeren starter. Grunnen
til omveien er at NOMAD binder en vertsmappe til `/data`, og en bind-mount får
ikke bildets innhold kopiert inn slik et navngitt volum får. Vil du bake inn en
annen modell: `--build-arg SEED_MODEL=NbAiLab/nb-whisper-medium`.

CI (`.github/workflows/docker.yml`) bygger bildet for amd64 og arm64 ved hver
`v*`-tagg og publiserer det til `ghcr.io/krfuro/commscribe`. Pakken må stå som
**offentlig** i GitHub (Packages → commscribe → Package settings → Change
visibility), ellers får NOMAD-serveren 401 når den prøver å hente den.

### Miljøvariabler

| Variabel | Standard i bildet | Betyr |
|---|---|---|
| `COMMSCRIBE_HOST` | `0.0.0.0` | Grensesnitt tjenesten lytter på |
| `COMMSCRIBE_PORT` | `8420` | Port inne i containeren |
| `COMMSCRIBE_NO_TOKEN` | `1` | Adgangskontroll av |
| `COMMSCRIBE_TOKEN` | *(tom)* | Fast øktnøkkel, hvis adgangskontroll er på |
| `COMMSCRIBE_DATA_DIR` | `/data` | Database, opptak, innstillinger, modeller |
| `COMMSCRIBE_MODEL_SEED` | `/opt/commscribe/models` | Modeller som kopieres inn ved første start |
| `COMMSCRIBE_OLLAMA_URL` | `http://nomad_ollama:11434` | Ollama-adressen, kan endres i UI-et |

## Veien inn i NOMADs katalog

Målet er at Commscribe står i Supply Depot som en vanlig app, uten at brukeren
skriver inn et bildenavn. Katalogen er en liste i NOMADs eget repo
(`admin/database/seeders/service_seeder.ts`), og en app kommer inn gjennom en
issue og en pull request dit — [CONTRIBUTING.md](https://github.com/Crosstalk-Solutions/project-nomad/blob/main/CONTRIBUTING.md)
ber om en issue før koden. Oppføringen ser slik ut, i samme form som Stirling
PDF og IT Tools (portene 8400–8499 er reservert for katalogen; 8460 er ledig):

```ts
{
  service_name: SERVICE_NAMES.COMMSCRIBE,          // 'nomad_commscribe'
  friendly_name: 'Commscribe',
  powered_by: 'Commscribe',
  display_order: 28,
  description: 'Offline speech-to-text — upload recordings, get transcripts and translations',
  icon: 'IconMicrophone',
  container_image: 'ghcr.io/krfuro/commscribe:1.1.0',
  source_repo: 'https://github.com/krfuro/commscribe',
  container_command: null,
  container_config: JSON.stringify({
    HostConfig: {
      RestartPolicy: { Name: 'unless-stopped' },
      PortBindings: { '8420/tcp': [{ HostPort: '8460' }] },
      Binds: [`${ServiceSeeder.NOMAD_STORAGE_ABS_PATH}/commscribe:/data`],
    },
    ExposedPorts: { '8420/tcp': {} },
  }),
  ui_location: '8460',
  installed: false,
  installation_status: 'idle',
  is_dependency_service: false,
  is_custom: false,
  category: 'productivity',
  depends_on: null,
  metadata: JSON.stringify({ minMemoryMB: 2048, minDiskMB: 4096 }),
},
```

Og avsnittet til `admin/docs/supply-depot-apps.md`, på engelsk som resten av
den fila:

> ## Commscribe
>
> Offline speech-to-text for recordings. Upload an audio file (a meeting, a
> dictation, a radio log exported from another device) and Commscribe
> transcribes it on your NOMAD with a Whisper model — Norwegian-trained by
> default, multilingual models available. Transcripts can be edited, searched,
> starred and exported as text, Markdown, CSV, SRT or JSON. Translation to
> English is built in; other languages go through the AI Assistant's Ollama
> if it is installed.
>
> **Official site / source:** [github.com/krfuro/commscribe](https://github.com/krfuro/commscribe)
>
> **First time you open it:** No login. A short wizard picks the speech model;
> the default (`nb-whisper-small`, ~480 MB) ships inside the image, so it
> works with no internet from the first start. Larger models can be
> downloaded from Settings → Models while online.
>
> **Where files end up:** `storage/commscribe` — database, audio (converted to
> 16 kHz WAV, about 115 MB per hour) and models. Nothing leaves the device
> unless you deliberately add a cloud API key in Settings → Cloud.
>
> **Heads up:** Transcription runs on the CPU; expect roughly real time on a
> modest machine (an hour of audio takes about an hour). The container has no
> audio input — live radio logging is what the desktop app is for.

Før PR-en sendes bør bildet ha vært kjørt som egendefinert app på en ekte
NOMAD gjennom minst én oppdatering, slik at både første installasjon og
oppgraderingsstien er sett virke.
