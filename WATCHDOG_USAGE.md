## Playwright Watchdog - Usage

This watchdog logs when Playwright runs start/exit and discovers a Chromium CDP WebSocket URL without editing your tests. It works on Windows and Linux.

### Install dependencies

- Windows: `pip install wmi pywin32`
- Linux: run as root for best fidelity (proc connector). Without root, it falls back to polling.

### Start the watchdog

```bash
python3 /home/mohamed/detector-rdpbridge/playwright_watchdog.py --verbose
```

Logs JSON lines to `~/.pw_watchdog/logs/watchdog.jsonl`.

### Enable CDP without changing tests

Chromium will expose a CDP port via runtime injectors.

- Node (Playwright Test):
```bash
PWDEBUG=1 NODE_OPTIONS="--require /home/mohamed/detector-rdpbridge/injectors/pw_injector.js" \
  npx playwright test --reporter=json,line --trace=retain-on-failure > ~/.pw_watchdog/reports/$(date +%s).json
```

- Python (pytest):
```bash
PWDEBUG=1 PYTHONPATH=/home/mohamed/detector-rdpbridge/injectors/pw_py_inject \
  PYTEST_ADDOPTS="--junitxml=$HOME/.pw_watchdog/reports/$(date +%s).xml" \
  pytest
```

Notes:
- `PWDEBUG=1` keeps the browser open on failure.
- Report files are optional; if provided, watchdog parses them to include failure messages and artifact paths.

### Example log entries

```json
{"ts":"2025-10-25T10:10:10Z","event":"playwright_started","os":"linux","runId":"abcd1234ef567890","pid":12345,"ppid":12222,"cmdline":"npx playwright test","cwd":"/work","user":"user","cdp":{"port":9231,"wsUrl":"ws://127.0.0.1:9231/devtools/browser/..."}}
{"ts":"2025-10-25T10:11:30Z","event":"playwright_failed","os":"linux","runId":"abcd1234ef567890","pid":12345,"exitCode":1,"durationMs":80234,"errors":[{"title":"should login","message":"expect(received).toBeVisible()","stack":"..."}],"artifacts":{"reportFile":"/home/user/.pw_watchdog/reports/1698234671.json","traceZip":["/work/test-results/trace.zip"],"screenshots":["/work/test-results/screenshot.png"]},"cdp":{"port":9231,"wsUrl":"ws://127.0.0.1:9231/devtools/browser/..."}}
```

### Run as a service

Linux (systemd user):
```bash
mkdir -p ~/.config/systemd/user
cp /home/mohamed/detector-rdpbridge/systemd/user/pw-watchdog.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pw-watchdog.service
journalctl --user -u pw-watchdog.service -f
```

Windows (Task Scheduler):
```powershell
powershell -ExecutionPolicy Bypass -File /home/mohamed/detector-rdpbridge/windows/install_watchdog_task.ps1
```


