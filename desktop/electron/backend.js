/**
 * Livssyklus for Python-sidevogna.
 *
 * Serveren velger sin egen ledige port og skriver ut en linje med port og
 * okt-nokkel. Vi leser den i stedet for a gjette pa en fast port, slik at to
 * apner samtidig ikke kolliderer og et opptatt 8420 ikke stopper oppstarten.
 */
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const readline = require('node:readline');

const READY_PREFIX = 'COMMSCRIBE_READY ';
const START_TIMEOUT_MS = 90_000;   // forste start pakker ut og laster biblioteker

class Backend {
  constructor({ isPackaged, resourcesPath, appRoot, onLog }) {
    this.isPackaged = isPackaged;
    this.resourcesPath = resourcesPath;
    this.appRoot = appRoot;
    this.onLog = onLog || (() => {});
    this.proc = null;
    this.info = null;
    this.stopping = false;
  }

  /** Kjorbar + argumenter, avhengig av om vi kjorer pakket eller fra kildekode. */
  command() {
    if (this.isPackaged) {
      const exe = process.platform === 'win32'
        ? 'commscribe-backend.exe' : 'commscribe-backend';
      const bin = path.join(this.resourcesPath, 'backend', exe);
      if (!fs.existsSync(bin)) {
        throw new Error(`Fant ikke tjenesten i pakken: ${bin}`);
      }
      return { cmd: bin, args: [], cwd: path.dirname(bin) };
    }

    // Utvikling: bruk prosjektets virtuelle milj0 hvis det finnes.
    const root = path.resolve(this.appRoot, '..');
    const venv = process.platform === 'win32'
      ? path.join(root, '.venv', 'Scripts', 'python.exe')
      : path.join(root, '.venv', 'bin', 'python');
    const python = fs.existsSync(venv)
      ? venv
      : (process.platform === 'win32' ? 'python' : 'python3');
    return { cmd: python, args: ['-m', 'backend'], cwd: root };
  }

  start() {
    const { cmd, args, cwd } = this.command();
    this.onLog(`starter tjenesten: ${cmd} ${args.join(' ')}`);

    // --watch-stdin: dor skallet uten a rekke a rydde, oppdager backenden det
    // pa at roret ryker, og avslutter selv.
    this.proc = spawn(cmd, [...args, '--port', '0', '--watch-stdin'], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
      windowsHide: true,
    });

    readline.createInterface({ input: this.proc.stderr })
      .on('line', (line) => this.onLog(`[py] ${line}`));

    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (fn, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        fn(value);
      };

      const timer = setTimeout(() => {
        finish(reject, new Error('Tjenesten svarte ikke innen tidsfristen.'));
      }, START_TIMEOUT_MS);

      readline.createInterface({ input: this.proc.stdout }).on('line', (line) => {
        this.onLog(`[py] ${line}`);
        if (line.startsWith(READY_PREFIX)) {
          try {
            this.info = JSON.parse(line.slice(READY_PREFIX.length));
            finish(resolve, this.info);
          } catch (err) {
            finish(reject, new Error(`Uleselig oppstartslinje: ${err.message}`));
          }
        }
      });

      this.proc.on('error', (err) => finish(reject, err));
      this.proc.on('exit', (code, signal) => {
        this.proc = null;
        if (this.stopping) return;
        finish(reject, new Error(
          `Tjenesten avsluttet uventet (kode ${code ?? signal}).`));
      });
    });
  }

  /** Sett i gang avslutning. Vi ber pent forst, og tvinger bare hvis den henger. */
  stop() {
    if (!this.proc) return;
    this.stopping = true;
    const proc = this.proc;
    try {
      // Windows har ingen SIGTERM. Der lukker vi stdin i stedet, og backenden
      // avslutter selv naar roret ryker.
      if (process.platform === 'win32') proc.stdin.end();
      else proc.kill('SIGTERM');
    } catch { /* prosessen er allerede borte */ }

    setTimeout(() => {
      try { if (!proc.killed) proc.kill('SIGKILL'); } catch { /* ok */ }
    }, 4000).unref?.();

    this.proc = null;
  }
}

module.exports = { Backend };
