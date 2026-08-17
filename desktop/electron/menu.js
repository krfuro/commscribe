/** Programmenyen. Norsk, og med de snarveiene folk forventer per plattform. */
const { Menu, shell, app, dialog } = require('electron');

const isMac = process.platform === 'darwin';

function buildMenu({ win, send, dataDir, logDir, version }) {
  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { label: `Om ${app.name}`, click: () => about(win, version) },
        { type: 'separator' },
        {
          label: 'Innstillinger …', accelerator: 'Cmd+,',
          click: () => send('settings'),
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { label: 'Skjul Commscribe', role: 'hide' },
        { label: 'Skjul andre', role: 'hideOthers' },
        { label: 'Vis alle', role: 'unhide' },
        { type: 'separator' },
        { label: 'Avslutt Commscribe', role: 'quit' },
      ],
    }] : []),

    {
      label: 'Fil',
      submenu: [
        {
          label: 'Start / stopp lytting', accelerator: 'CmdOrCtrl+L',
          click: () => send('toggle'),
        },
        { type: 'separator' },
        {
          label: 'Åpne datamappa',
          click: () => shell.openPath(dataDir),
        },
        {
          label: 'Åpne loggmappa',
          click: () => shell.openPath(logDir),
        },
        { type: 'separator' },
        ...(isMac
          ? [{ label: 'Lukk vindu', role: 'close' }]
          : [
              {
                label: 'Innstillinger …', accelerator: 'Ctrl+,',
                click: () => send('settings'),
              },
              { type: 'separator' },
              { label: 'Avslutt', role: 'quit' },
            ]),
      ],
    },

    {
      label: 'Rediger',
      submenu: [
        { label: 'Angre', role: 'undo' },
        { label: 'Gjør om', role: 'redo' },
        { type: 'separator' },
        { label: 'Klipp ut', role: 'cut' },
        { label: 'Kopier', role: 'copy' },
        { label: 'Lim inn', role: 'paste' },
        { label: 'Merk alt', role: 'selectAll' },
        { type: 'separator' },
        {
          label: 'Søk i loggen', accelerator: 'CmdOrCtrl+F',
          click: () => send('search'),
        },
      ],
    },

    {
      label: 'Vis',
      submenu: [
        { label: 'Last inn på nytt', role: 'reload' },
        { type: 'separator' },
        { label: 'Zoom inn', role: 'zoomIn' },
        { label: 'Zoom ut', role: 'zoomOut' },
        { label: 'Normal størrelse', role: 'resetZoom' },
        { type: 'separator' },
        { label: 'Fullskjerm', role: 'togglefullscreen' },
        { label: 'Utviklerverktøy', role: 'toggleDevTools' },
      ],
    },

    {
      label: 'Vindu',
      submenu: [
        { label: 'Minimer', role: 'minimize' },
        ...(isMac
          ? [{ label: 'Zoom', role: 'zoom' }, { type: 'separator' },
             { label: 'Hent alle fram', role: 'front' }]
          : [{ label: 'Lukk', role: 'close' }]),
      ],
    },

    {
      role: 'help',
      label: 'Hjelp',
      submenu: [
        {
          label: 'Kom i gang',
          click: () => shell.openExternal(
            'https://github.com/krfuro/commscribe#kom-i-gang'),
        },
        ...(isMac ? [] : [{ label: 'Om Commscribe', click: () => about(win, version) }]),
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function about(win, version) {
  dialog.showMessageBox(win, {
    type: 'info',
    title: 'Om Commscribe',
    message: 'Commscribe',
    detail: `Sambandslogg med sanntids transkribering.\n\nVersjon ${version}\n` +
            `Electron ${process.versions.electron} · Chromium ${process.versions.chrome}`,
    buttons: ['OK'],
  });
}

module.exports = { buildMenu };
