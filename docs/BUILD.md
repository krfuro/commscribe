# Bygge Commscribe

Commscribe er to deler som pakkes til én app:

| Del | Hva | Verktøy |
|---|---|---|
| Tjenesten | Python: lydfangst, segmentering, Whisper, SQLite, HTTP/WebSocket | PyInstaller |
| Skallet | Electron: vindu, meny, ikon, installasjonsfil | electron-builder |

Skallet starter tjenesten som en underprosess, leser porten den melder tilbake,
og viser grensesnittet den serverer. Brukeren ser én app.

## Viktig: installasjonsfiler kan ikke krysskompileres

PyInstaller pakker maskinkode, og `.app`/`.exe` må bygges på plattformen de skal
kjøre på. Du kan ikke lage en Windows-installer på en Mac.

To måter å få begge:

1. **GitHub Actions** (anbefalt) — `.github/workflows/build.yml` bygger for
   macOS på Apple Silicon, macOS på Intel og Windows på hvert push. Filene
   ligger under *Artifacts* på kjøringen. Push en tagg som `v1.0.0`, og de
   legges også ved som et utkast til utgivelse.
2. **Lokalt på hver maskin** — følg oppskriften under, én gang per plattform.

## Forutsetninger

- Python 3.11 eller 3.12
- Node 20 eller nyere
- Windows: ingenting mer. macOS: Xcode kommandolinjeverktøy (`xcode-select --install`)

## Bygge lokalt

```bash
# 1. Python-avhengigheter
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install "pyinstaller>=6.11" pyinstaller-hooks-contrib

# 2. Pakk tjenesten
.venv/bin/pyinstaller --noconfirm --clean packaging/commscribe-backend.spec \
  --distpath desktop/resources/backend-dist --workpath build/pyinstaller

# 3. Sjekk at pakken er komplett før du går videre
.venv/bin/python packaging/verify_backend.py

# 4. Bygg installasjonsfila
cd desktop
npm install
npm run dist:mac      # eller dist:win / dist:linux
```

Resultatet havner i `dist/`:

- macOS: `Commscribe-1.0.0-mac-arm64.dmg` (dra ikonet til Programmer)
- Windows: `Commscribe-1.0.0-win-x64.exe` (installerer per bruker, uten UAC)
- Linux: `.AppImage` og `.deb`

## Utvikling uten å pakke

```bash
# Tjenesten i nettleseren
./run.sh                      # http://127.0.0.1:8420

# Eller med skallet rundt, mot kildekoden
cd desktop && npm install && npm start
```

I utviklingsmodus finner skallet `.venv` i prosjektmappa og kjører
`python -m backend` derfra — ingen PyInstaller nødvendig.

## Når appen ikke starter

Tjenesten har en selvtest som sier hvilket bibliotek som mangler:

```bash
# macOS
/Applications/Commscribe.app/Contents/Resources/backend/commscribe-backend --selftest
# Windows
"%LOCALAPPDATA%\Programs\Commscribe\resources\backend\commscribe-backend.exe" --selftest
```

Loggene ligger i:

- macOS: `~/Library/Logs/Commscribe/`
- Windows: `%APPDATA%\Commscribe\logs\`

`desktop.log` er skallet, `commscribe-*.log` er tjenesten.

## Signering og notarisering

Bygget virker usignert, men da må brukeren klikke bort en advarsel første gang.
CI bygger usignert (`CSC_IDENTITY_AUTO_DISCOVERY=false`). For en ordentlig
utgivelse:

**macOS** — krever Apple Developer-medlemskap. Legg disse inn som
repository secrets og fjern `CSC_IDENTITY_AUTO_DISCOVERY` fra workflowen:

| Secret | Hva |
|---|---|
| `CSC_LINK` | Developer ID Application-sertifikatet som base64 av en `.p12` |
| `CSC_KEY_PASSWORD` | passordet til `.p12`-fila |
| `APPLE_ID` | Apple-ID-en som notariserer |
| `APPLE_APP_SPECIFIC_PASSWORD` | app-spesifikt passord fra appleid.apple.com |
| `APPLE_TEAM_ID` | team-ID-en |

Legg så til i `electron-builder.yml`:

```yaml
mac:
  notarize:
    teamId: ${env.APPLE_TEAM_ID}
```

Entitlements ligger klare i `desktop/build/entitlements.mac.plist`.
`com.apple.security.cs.disable-library-validation` er nødvendig fordi
tjenesten er en egen kjørbar med sine egne biblioteker — uten den nekter
hardened runtime å laste dem.

**Windows** — sett `CSC_LINK` og `CSC_KEY_PASSWORD` til et
kodesigneringssertifikat. Uten det viser SmartScreen en advarsel til appen har
opparbeidet omdømme.

## Endre ikonet

`desktop/build/icon.png` (1024×1024) er kilden; electron-builder lager `.icns`
og `.ico` selv. Ikonet er tegnet av et skript:

```bash
.venv/bin/pip install Pillow
.venv/bin/python packaging/make_icon.py
```

## Versjonsnummer

Står i `desktop/package.json` (appen og installasjonsfila) og
`backend/main.py` som `APP_VERSION` (API og statuslinje). Hold dem like.
