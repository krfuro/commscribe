/**
 * Broen mellom skallet og grensesnittet.
 *
 * Renderen kjorer uten Node-tilgang. Alt den skal kunne be skallet om ligger
 * her, eksplisitt og navngitt - ingen generell tilgang til ipcRenderer.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('commscribe', {
  platform: process.platform,

  /** Vis en av appens egne mapper i Finder/Utforsker. */
  openPath: (target) => ipcRenderer.invoke('open-path', target),

  /** Menyvalg fra skallet: 'settings' | 'toggle' | 'search'. */
  onMenu: (handler) => {
    ipcRenderer.on('menu', (_event, action) => handler(action));
  },

  /** Grensesnittet byttet spraak - menyen skal folge med. */
  setLanguage: (lang) => ipcRenderer.send('set-language', String(lang || 'en')),

});

// Tittellinja tegnes av oss, men trafikklys og vindusknapper kommer fra
// systemet. Merk kroppen sa CSS-en kan gi dem plass.
window.addEventListener('DOMContentLoaded', () => {
  const cls = { darwin: 'is-mac', win32: 'is-win' }[process.platform];
  if (cls) document.body.classList.add(cls);
});
