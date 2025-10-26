/*
  Playwright Node injector (preload) to ensure Chromium exposes a CDP port
  and to persist the ws URL for the watchdog. Does not modify test code.

  Usage:
    NODE_OPTIONS=--require /absolute/path/to/injectors/pw_injector.js npx playwright test
*/
const fs = require('fs');
const os = require('os');
const path = require('path');
const http = require('http');
const net = require('net');

const WATCHDOG_DIR = path.join(os.homedir(), '.pw_watchdog');
const CDP_DIR = path.join(WATCHDOG_DIR, 'cdp');
fs.mkdirSync(CDP_DIR, { recursive: true });

function envTrue(name) {
  const v = process.env[name];
  if (!v) return false;
  return ['1', 'true', 'yes', 'on'].includes(String(v).toLowerCase());
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

function fetchWsUrl(port) {
  return new Promise((resolve) => {
    const req = http.get({ host: '127.0.0.1', port, path: '/json/version', timeout: 500 }, (res) => {
      let data = '';
      res.setEncoding('utf8');
      res.on('data', (c) => (data += c));
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json.webSocketDebuggerUrl || null);
        } catch (e) {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => {
      req.destroy();
      resolve(null);
    });
  });
}

async function ensureCDPArgs(options) {
  const opts = options || {};
  const isHeadlessSet = Object.prototype.hasOwnProperty.call(opts, 'headless');
  if (!isHeadlessSet && envTrue('PWDEBUG')) {
    opts.headless = false;
  }
  const args = Array.isArray(opts.args) ? opts.args.slice() : [];
  if (!args.some(a => /--remote-debugging-port(=|\s)\d+/.test(a))) {
    const port = await getFreePort();
    args.push(`--remote-debugging-port=${port}`);
    opts.__pw_watchdog_port = port;
  }
  opts.args = args;
  return opts;
}

async function writeCDPInfo(port) {
  const wsUrl = port ? await fetchWsUrl(port) : null;
  const out = { port, wsUrl };
  const file = path.join(CDP_DIR, `${process.pid}.json`);
  try { fs.writeFileSync(file, JSON.stringify(out), 'utf8'); } catch (_) {}
}

(function patchPlaywright() {
  try {
    const pw = require('playwright');
    if (!pw || !pw.chromium) return;
    const origLaunch = pw.chromium.launch.bind(pw.chromium);
    const origLaunchPersist = pw.chromium.launchPersistentContext.bind(pw.chromium);

    pw.chromium.launch = async function patchedLaunch(options) {
      const opts = await ensureCDPArgs(options);
      const browser = await origLaunch(opts);
      if (opts.__pw_watchdog_port) {
        writeCDPInfo(opts.__pw_watchdog_port);
      }
      return browser;
    };

    pw.chromium.launchPersistentContext = async function patchedLaunchPersist(userDataDir, options) {
      const opts = await ensureCDPArgs(options);
      const context = await origLaunchPersist(userDataDir, opts);
      if (opts.__pw_watchdog_port) {
        writeCDPInfo(opts.__pw_watchdog_port);
      }
      return context;
    };
  } catch (e) {
    // Swallow errors to avoid breaking user runs
  }
})();




