/** The application menu, in the language the user chose in the app.
 *  The shell reads the language from the service after start and rebuilds
 *  the menu when the interface changes it. */
const { Menu, shell, app, dialog } = require('electron');

const isMac = process.platform === 'darwin';

const STRINGS = {
  en: {
    about: 'About Commscribe', settings: 'Settings…', hide: 'Hide Commscribe',
    hideOthers: 'Hide Others', unhide: 'Show All', quit: 'Quit Commscribe', quitShort: 'Quit',
    file: 'File', toggle: 'Start / stop listening', openData: 'Open the data folder',
    openLogs: 'Open the log folder', closeWindow: 'Close Window',
    edit: 'Edit', undo: 'Undo', redo: 'Redo', cut: 'Cut', copy: 'Copy', paste: 'Paste',
    selectAll: 'Select All', search: 'Search the log',
    view: 'View', reload: 'Reload', zoomIn: 'Zoom In', zoomOut: 'Zoom Out',
    resetZoom: 'Actual Size', fullscreen: 'Full Screen', devTools: 'Developer Tools',
    window: 'Window', minimize: 'Minimize', zoom: 'Zoom', front: 'Bring All to Front',
    close: 'Close', help: 'Help', gettingStarted: 'Getting started',
    tagline: 'Radio log with real-time transcription.', version: 'Version',
    by: 'Produced by Furo Engineering',
  },
  nb: {
    about: 'Om Commscribe', settings: 'Innstillinger …', hide: 'Skjul Commscribe',
    hideOthers: 'Skjul andre', unhide: 'Vis alle', quit: 'Avslutt Commscribe', quitShort: 'Avslutt',
    file: 'Fil', toggle: 'Start / stopp lytting', openData: 'Åpne datamappa',
    openLogs: 'Åpne loggmappa', closeWindow: 'Lukk vindu',
    edit: 'Rediger', undo: 'Angre', redo: 'Gjør om', cut: 'Klipp ut', copy: 'Kopier', paste: 'Lim inn',
    selectAll: 'Merk alt', search: 'Søk i loggen',
    view: 'Vis', reload: 'Last inn på nytt', zoomIn: 'Zoom inn', zoomOut: 'Zoom ut',
    resetZoom: 'Normal størrelse', fullscreen: 'Fullskjerm', devTools: 'Utviklerverktøy',
    window: 'Vindu', minimize: 'Minimer', zoom: 'Zoom', front: 'Hent alle fram',
    close: 'Lukk', help: 'Hjelp', gettingStarted: 'Kom i gang',
    tagline: 'Sambandslogg med sanntids transkribering.', version: 'Versjon',
    by: 'Produsert av Furo Engineering',
  },
  sv: {
    about: 'Om Commscribe', settings: 'Inställningar …', hide: 'Göm Commscribe',
    hideOthers: 'Göm övriga', unhide: 'Visa alla', quit: 'Avsluta Commscribe', quitShort: 'Avsluta',
    file: 'Arkiv', toggle: 'Starta / stoppa lyssning', openData: 'Öppna datamappen',
    openLogs: 'Öppna loggmappen', closeWindow: 'Stäng fönster',
    edit: 'Redigera', undo: 'Ångra', redo: 'Gör om', cut: 'Klipp ut', copy: 'Kopiera', paste: 'Klistra in',
    selectAll: 'Markera allt', search: 'Sök i loggen',
    view: 'Visa', reload: 'Läs in igen', zoomIn: 'Zooma in', zoomOut: 'Zooma ut',
    resetZoom: 'Normal storlek', fullscreen: 'Helskärm', devTools: 'Utvecklarverktyg',
    window: 'Fönster', minimize: 'Minimera', zoom: 'Zooma', front: 'Lägg alla främst',
    close: 'Stäng', help: 'Hjälp', gettingStarted: 'Kom igång',
    tagline: 'Radiologg med transkribering i realtid.', version: 'Version',
    by: 'Producerad av Furo Engineering',
  },
  de: {
    about: 'Über Commscribe', settings: 'Einstellungen …', hide: 'Commscribe ausblenden',
    hideOthers: 'Andere ausblenden', unhide: 'Alle einblenden', quit: 'Commscribe beenden', quitShort: 'Beenden',
    file: 'Datei', toggle: 'Mithören starten / stoppen', openData: 'Datenordner öffnen',
    openLogs: 'Protokollordner öffnen', closeWindow: 'Fenster schließen',
    edit: 'Bearbeiten', undo: 'Widerrufen', redo: 'Wiederholen', cut: 'Ausschneiden', copy: 'Kopieren', paste: 'Einsetzen',
    selectAll: 'Alles auswählen', search: 'Im Logbuch suchen',
    view: 'Darstellung', reload: 'Neu laden', zoomIn: 'Vergrößern', zoomOut: 'Verkleinern',
    resetZoom: 'Originalgröße', fullscreen: 'Vollbild', devTools: 'Entwicklerwerkzeuge',
    window: 'Fenster', minimize: 'Im Dock ablegen', zoom: 'Zoomen', front: 'Alle nach vorne bringen',
    close: 'Schließen', help: 'Hilfe', gettingStarted: 'Erste Schritte',
    tagline: 'Funklogbuch mit Transkription in Echtzeit.', version: 'Version',
    by: 'Hergestellt von Furo Engineering',
  },
  fr: {
    about: 'À propos de Commscribe', settings: 'Réglages…', hide: 'Masquer Commscribe',
    hideOthers: 'Masquer les autres', unhide: 'Tout afficher', quit: 'Quitter Commscribe', quitShort: 'Quitter',
    file: 'Fichier', toggle: "Démarrer / arrêter l'écoute", openData: 'Ouvrir le dossier de données',
    openLogs: 'Ouvrir le dossier des journaux', closeWindow: 'Fermer la fenêtre',
    edit: 'Édition', undo: 'Annuler', redo: 'Rétablir', cut: 'Couper', copy: 'Copier', paste: 'Coller',
    selectAll: 'Tout sélectionner', search: 'Rechercher dans le journal',
    view: 'Présentation', reload: 'Recharger', zoomIn: 'Zoom avant', zoomOut: 'Zoom arrière',
    resetZoom: 'Taille réelle', fullscreen: 'Plein écran', devTools: 'Outils de développement',
    window: 'Fenêtre', minimize: 'Réduire', zoom: 'Zoom', front: 'Tout ramener au premier plan',
    close: 'Fermer', help: 'Aide', gettingStarted: 'Premiers pas',
    tagline: 'Journal radio avec transcription en temps réel.', version: 'Version',
    by: 'Produit par Furo Engineering',
  },
  es: {
    about: 'Acerca de Commscribe', settings: 'Ajustes…', hide: 'Ocultar Commscribe',
    hideOthers: 'Ocultar otros', unhide: 'Mostrar todo', quit: 'Salir de Commscribe', quitShort: 'Salir',
    file: 'Archivo', toggle: 'Iniciar / detener la escucha', openData: 'Abrir la carpeta de datos',
    openLogs: 'Abrir la carpeta de registros', closeWindow: 'Cerrar ventana',
    edit: 'Edición', undo: 'Deshacer', redo: 'Rehacer', cut: 'Cortar', copy: 'Copiar', paste: 'Pegar',
    selectAll: 'Seleccionar todo', search: 'Buscar en el registro',
    view: 'Visualización', reload: 'Recargar', zoomIn: 'Ampliar', zoomOut: 'Reducir',
    resetZoom: 'Tamaño real', fullscreen: 'Pantalla completa', devTools: 'Herramientas de desarrollo',
    window: 'Ventana', minimize: 'Minimizar', zoom: 'Zoom', front: 'Traer todo al frente',
    close: 'Cerrar', help: 'Ayuda', gettingStarted: 'Primeros pasos',
    tagline: 'Registro de radio con transcripción en tiempo real.', version: 'Versión',
    by: 'Producido por Furo Engineering',
  },
};

function strings(lang) {
  return STRINGS[lang] || STRINGS.en;
}

function buildMenu({ win, send, dataDir, logDir, version, lang = 'en' }) {
  const s = strings(lang);
  const template = [
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { label: s.about, click: () => about(win, version, lang) },
        { type: 'separator' },
        { label: s.settings, accelerator: 'Cmd+,', click: () => send('settings') },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { label: s.hide, role: 'hide' },
        { label: s.hideOthers, role: 'hideOthers' },
        { label: s.unhide, role: 'unhide' },
        { type: 'separator' },
        { label: s.quit, role: 'quit' },
      ],
    }] : []),

    {
      label: s.file,
      submenu: [
        { label: s.toggle, accelerator: 'CmdOrCtrl+L', click: () => send('toggle') },
        { type: 'separator' },
        { label: s.openData, click: () => shell.openPath(dataDir) },
        { label: s.openLogs, click: () => shell.openPath(logDir) },
        { type: 'separator' },
        ...(isMac
          ? [{ label: s.closeWindow, role: 'close' }]
          : [
              { label: s.settings, accelerator: 'Ctrl+,', click: () => send('settings') },
              { type: 'separator' },
              { label: s.quitShort, role: 'quit' },
            ]),
      ],
    },

    {
      label: s.edit,
      submenu: [
        { label: s.undo, role: 'undo' },
        { label: s.redo, role: 'redo' },
        { type: 'separator' },
        { label: s.cut, role: 'cut' },
        { label: s.copy, role: 'copy' },
        { label: s.paste, role: 'paste' },
        { label: s.selectAll, role: 'selectAll' },
        { type: 'separator' },
        { label: s.search, accelerator: 'CmdOrCtrl+F', click: () => send('search') },
      ],
    },

    {
      label: s.view,
      submenu: [
        { label: s.reload, role: 'reload' },
        { type: 'separator' },
        { label: s.zoomIn, role: 'zoomIn' },
        { label: s.zoomOut, role: 'zoomOut' },
        { label: s.resetZoom, role: 'resetZoom' },
        { type: 'separator' },
        { label: s.fullscreen, role: 'togglefullscreen' },
        { label: s.devTools, role: 'toggleDevTools' },
      ],
    },

    {
      label: s.window,
      submenu: [
        { label: s.minimize, role: 'minimize' },
        ...(isMac
          ? [{ label: s.zoom, role: 'zoom' }, { type: 'separator' },
             { label: s.front, role: 'front' }]
          : [{ label: s.close, role: 'close' }]),
      ],
    },

    {
      role: 'help',
      label: s.help,
      submenu: [
        {
          label: s.gettingStarted,
          click: () => shell.openExternal('https://github.com/krfuro/commscribe#getting-started'),
        },
        ...(isMac ? [] : [{ label: s.about, click: () => about(win, version, lang) }]),
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function about(win, version, lang = 'en') {
  const s = strings(lang);
  dialog.showMessageBox(win, {
    type: 'info',
    title: s.about,
    message: 'Commscribe',
    detail: `${s.tagline}\n${s.by}\n\n${s.version} ${version}\n` +
            `Electron ${process.versions.electron} · Chromium ${process.versions.chrome}\n\n` +
            'Apache License 2.0',
    buttons: ['OK'],
  });
}

module.exports = { buildMenu, STRINGS };
