/**
 * Commscribe - skrivebordsskall.
 *
 * Electron eier vinduet og menyene; all lyd, transkribering og lagring skjer i
 * Python-sidevogna. Skallet starter den, venter pa at den melder seg klar, og
 * viser grensesnittet den serverer.
 */
const { app, BrowserWindow, ipcMain, shell, dialog, systemPreferences, session } =
  require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { Backend } = require('./backend');
const { buildMenu } = require('./menu');

const isMac = process.platform === 'darwin';
const isWin = process.platform === 'win32';

let win = null;
let backend = null;
let quitting = false;

// Loggen fra skallet legges ved siden av backendens egen logg.
const logDir = path.join(app.getPath('userData'), 'logs');
fs.mkdirSync(logDir, { recursive: true });
const logFile = path.join(logDir, 'desktop.log');

function log(message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  process.stdout.write(line);
  try { fs.appendFileSync(logFile, line); } catch { /* loggen er ikke kritisk */ }
}

/* ---------- vindu ---------- */

function createWindow() {
  win = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 720,
    minHeight: 520,
    show: false,
    backgroundColor: '#080d14',        // hindrer hvitt glimt for siden males
    title: 'Commscribe',
    icon: isWin ? path.join(__dirname, '..', 'build', 'icon.ico') : undefined,
    // Vi tegner tittellinja selv. macOS legger trafikklysene oppa vaar egen,
    // Windows far de innebygde knappene via overlegget.
    titleBarStyle: isMac ? 'hiddenInset' : (isWin ? 'hidden' : 'default'),
    trafficLightPosition: isMac ? { x: 14, y: 12 } : undefined,
    titleBarOverlay: isWin
      ? { color: '#0c1119', symbolColor: '#9fb3c8', height: 38 }
      : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
  });

  win.once('ready-to-show', () => win.show());

  // Alt som ikke er vaart eget grensesnitt hoerer hjemme i nettleseren.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    const allowed = backend?.info?.url;
    if (allowed && !url.startsWith(new URL(allowed).origin)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  win.on('closed', () => {
    win = null;
    if (!quitting) app.quit();
  });

  return win;
}

/** Enkel oppstartsskjerm mens Python laster - forste start tar noen sekunder. */
function showBooting(message = 'Starter tjenesten …') {
  const html = `<!doctype html><meta charset="utf-8">
  <style>
    html,body{height:100%;margin:0}
    body{background:#080d14;color:#9fb3c8;display:flex;flex-direction:column;
      align-items:center;justify-content:center;gap:18px;
      font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
      -webkit-app-region:drag}
    .name{font-size:12.5px;font-weight:600;letter-spacing:.32em;color:#45c8f0}
    .ring{width:26px;height:26px;border:2px solid #21303f;border-top-color:#45c8f0;
      border-radius:50%;animation:s .8s linear infinite}
    @keyframes s{to{transform:rotate(360deg)}}
    p{margin:0;font-size:13px}
  </style>
  <div class="name">COMMSCRIBE</div>
  <div class="ring"></div>
  <p>${message}</p>`;
  win.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
}

/** Spraaket brukeren har valgt, lest fra tjenesten. Engelsk hvis noe feiler. */
async function readLanguage(info) {
  try {
    const res = await fetch(new URL('/api/config', info.url), {
      headers: info.token ? { 'X-Commscribe-Token': info.token } : {},
    });
    const config = await res.json();
    return config.ui_language || 'en';
  } catch (err) {
    log(`fikk ikke lest spraak: ${err.message}`);
    return 'en';
  }
}

/* ---------- mikrofontilgang ---------- */


async function ensureMicrophone() {
  if (!isMac) return true;
  // macOS knytter mikrofontillatelsen til app-bunten. Python-prosessen arver
  // den fra oss, men bare hvis vi har spurt - ellers far den bare stillhet,
  // uten feilmelding, og appen ser ut som den ikke virker.
  const status = systemPreferences.getMediaAccessStatus('microphone');
  if (status === 'granted') return true;
  if (status === 'denied') {
    const { response } = await dialog.showMessageBox({
      type: 'warning',
      title: 'Mikrofontilgang mangler',
      message: 'Commscribe far ikke tilgang til lydinngangen.',
      detail: 'Gi tilgang under Systeminnstillinger → Personvern og sikkerhet → '
            + 'Mikrofon, og start Commscribe pa nytt.',
      buttons: ['Apne systeminnstillinger', 'Fortsett likevel'],
      defaultId: 0,
    });
    if (response === 0) {
      shell.openExternal(
        'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone');
    }
    return false;
  }
  return systemPreferences.askForMediaAccess('microphone');
}

/* ---------- oppstart ---------- */

async function boot() {
  createWindow();
  showBooting();

  backend = new Backend({
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    appRoot: app.getAppPath(),
    onLog: log,
  });

  try {
    await ensureMicrophone();
    const info = await backend.start();
    log(`tjenesten er klar pa ${info.url}`);
    await win.loadURL(info.url);

    // Menyen skal staa paa samme spraak som grensesnittet. Spraaket bor i
    // tjenestens innstillinger, saa vi sporr den - med oktnokkelen, som
    // ellers ville stengt oss ute fra vaart eget API.
    const menuFor = (lang) => buildMenu({
      win,
      send: (action) => win?.webContents.send('menu', action),
      dataDir: app.getPath('userData'),
      logDir,
      version: app.getVersion(),
      lang,
    });
    menuFor(await readLanguage(info));
    ipcMain.on('set-language', (_event, lang) => menuFor(lang));
  } catch (err) {
    log(`oppstart feilet: ${err.stack || err.message}`);
    showBooting('Kunne ikke starte tjenesten.');
    await dialog.showMessageBox(win, {
      type: 'error',
      title: 'Commscribe kunne ikke starte',
      message: 'Tjenesten som gjor jobben startet ikke.',
      detail: `${err.message}\n\nLoggen ligger i:\n${logDir}`,
      buttons: ['Apne loggmappa', 'Avslutt'],
      defaultId: 0,
    }).then(({ response }) => {
      if (response === 0) shell.openPath(logDir);
    });
    app.quit();
  }
}

/* ---------- app-livssyklus ---------- */

// To kopier ville kjempet om samme database og lydenhet. Den andre skal i
// stedet lofte fram vinduet som allerede star apent.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!win) return;
    if (win.isMinimized()) win.restore();
    win.focus();
  });

  app.whenReady().then(() => {
    // Renderen ber aldri om enheter selv, men be om mikrofon skal uansett
    // aldri ga stille gjennom.
    session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => {
      cb(permission === 'media');
    });

    boot();

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) boot();
    });
  });

  app.on('window-all-closed', () => app.quit());

  app.on('before-quit', () => {
    quitting = true;
    backend?.stop();
  });

  // Sikkerhetsnett: blir skallet drept, skal ikke Python bli liggende igjen.
  // Backenden overvaaker ogsaa stdin selv, men et ryddig SIGTERM lar den lukke
  // databasen og skrive ferdig det siste segmentet.
  process.on('exit', () => backend?.stop());
  for (const signal of ['SIGTERM', 'SIGINT', 'SIGHUP']) {
    process.on(signal, () => {
      log(`fikk ${signal}, avslutter`);
      quitting = true;
      backend?.stop();
      app.quit();
    });
  }
}

/* ---------- broer til grensesnittet ---------- */

ipcMain.handle('open-path', (_e, target) => {
  if (typeof target !== 'string' || !target) return false;
  // Bare mapper vi selv eier - renderen skal ikke kunne apne hva som helst.
  const allowed = [app.getPath('userData'), logDir];
  const resolved = path.resolve(target);
  if (!allowed.some((base) => resolved === base || resolved.startsWith(base + path.sep))) {
    log(`avviste apning av ${resolved}`);
    return false;
  }
  shell.openPath(resolved);
  return true;
});

ipcMain.handle('platform', () => process.platform);
