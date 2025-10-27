# Playwright Watchdog - Quick Reference

## One-Liner Commands

### Installation
```bash
# Install deps and setup
./install.sh

# Or manual deps
pip install -r requirements.txt
# OR: sudo apt install python3-psutil python3-dotenv
```

### Start Watchdog
```bash
# Foreground
./playwright_watchdog.py

# Background
nohup ./playwright_watchdog.py &

# As service (Linux)
systemctl --user enable --now pw-watchdog
```

### Run Tests
```bash
# Node.js
./bin/pw-run.sh [playwright args...]

# Python
./bin/pw-run-pytest.sh [pytest args...]
```

### View Logs
```bash
# Tail JSONL
tail -f ~/.pw_watchdog/logs/watchdog.jsonl

# Pretty print
tail -f ~/.pw_watchdog/logs/watchdog.jsonl | jq .

# Show only failures
jq 'select(.event == "playwright_failed")' ~/.pw_watchdog/logs/watchdog.jsonl
```

### Get CDP URLs
```bash
# Latest
jq -r 'select(.event == "playwright_started") | .cdp.wsUrl' \
  ~/.pw_watchdog/logs/watchdog.jsonl | tail -1

# All from today
jq -r 'select(.event == "playwright_started" and .ts >= "2025-10-26") | .cdp.wsUrl' \
  ~/.pw_watchdog/logs/watchdog.jsonl
```

## File Locations

| Path | Description |
|------|-------------|
| `~/.pw_watchdog/logs/watchdog.jsonl` | Main event log |
| `~/.pw_watchdog/cdp/<runId>.json` | CDP metadata per run |
| `~/.pw_watchdog/reports/<runId>.*` | Test reports (JSON/XML) |
| `.env` | Configuration |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PW_WATCHDOG_DIR` | `~/.pw_watchdog` | Base directory |
| `PW_WATCHDOG_RUN_ID` | auto | Override runId |
| `PW_WATCHDOG_REPORT_FILE` | auto | Report path |
| `PW_WATCHDOG_STDOUT` | `1` | Console logging |
| `PW_WATCHDOG_POLL_INTERVAL` | `0.5` | Poll frequency (sec) |
| `PWDEBUG` | `1` | Keep browser open |
| `NODE_OPTIONS` | `--require ...` | Node injector |
| `PYTHONPATH` | `.../pw_py_inject` | Python injector |

## Event Types

| Event | When | Key Fields |
|-------|------|------------|
| `playwright_started` | Test run begins | `runId`, `pid`, `cdp.wsUrl` |
| `playwright_failed` | Test fails | `exitCode`, `error`, `artifacts` |
| `playwright_succeeded` | Test passes | `exitCode`, `durationMs` |

## Manual Test Run

### Node.js
```bash
RUNID=$(date +%s%3N)-$$
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
PW_WATCHDOG_REPORT_FILE="$HOME/.pw_watchdog/reports/$RUNID.json" \
NODE_OPTIONS="--require $(pwd)/injectors/pw_injector.js" \
npx playwright test --reporter=json,line --trace=retain-on-failure
```

### Python
```bash
RUNID=$(date +%s%3N)-$$
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
PYTHONPATH="$(pwd)/injectors/pw_py_inject" \
PYTEST_ADDOPTS="--junitxml=$HOME/.pw_watchdog/reports/$RUNID.xml" \
pytest
```

## jq Recipes

```bash
# Count events by type
jq -s 'group_by(.event) | map({event: .[0].event, count: length})' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Average test duration
jq -s 'map(select(.durationMs)) | add/length' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Failed tests today
jq -r 'select(.event == "playwright_failed" and .ts >= "2025-10-26") | 
  "\(.runId): \(.error.title)"' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Extract all trace files
jq -r 'select(.artifacts.traces) | .artifacts.traces[]' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Latest runId
jq -r .runId ~/.pw_watchdog/logs/watchdog.jsonl | tail -1
```

## CDP Connection (Node.js)

```javascript
const CDP = require('chrome-remote-interface');
const fs = require('fs');

// Read latest CDP info
const files = fs.readdirSync(`${process.env.HOME}/.pw_watchdog/cdp/`);
const latest = files.sort().pop();
const cdp = JSON.parse(fs.readFileSync(`${process.env.HOME}/.pw_watchdog/cdp/${latest}`));

// Connect
const client = await CDP({ target: cdp.wsUrl });
const { Page } = client;
await Page.enable();

// Screenshot
const shot = await Page.captureScreenshot();
fs.writeFileSync('debug.png', shot.data, 'base64');

await client.close();
```

## CDP Connection (Python)

```python
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Read latest CDP info
cdp_dir = Path.home() / '.pw_watchdog' / 'cdp'
latest = sorted(cdp_dir.glob('*.json'))[-1]
cdp_info = json.loads(latest.read_text())

# Connect
async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp(cdp_info['wsUrl'])
    page = browser.contexts[0].pages[0]
    await page.screenshot(path='debug.png')
```

## Service Management

### Linux (systemd)
```bash
# Status
systemctl --user status pw-watchdog

# Start/stop
systemctl --user start pw-watchdog
systemctl --user stop pw-watchdog

# Enable/disable autostart
systemctl --user enable pw-watchdog
systemctl --user disable pw-watchdog

# Logs
journalctl --user -u pw-watchdog -f
```

### Windows (Task Scheduler)
```powershell
# Status
Get-ScheduledTask -TaskName "PlaywrightWatchdog" | Get-ScheduledTaskInfo

# Start/stop
Start-ScheduledTask -TaskName "PlaywrightWatchdog"
Stop-ScheduledTask -TaskName "PlaywrightWatchdog"

# Remove
Unregister-ScheduledTask -TaskName "PlaywrightWatchdog" -Confirm:$false
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Module not found: psutil" | `pip install -r requirements.txt` |
| "externally-managed-environment" | Use venv: `python3 -m venv venv && source venv/bin/activate` |
| No CDP info | Use helper scripts: `./bin/pw-run.sh` |
| Watchdog not detecting | Check patterns match: `ps aux | grep playwright` |
| Permission denied | `chmod +x *.sh *.py` |

## Key Files

| File | Purpose |
|------|---------|
| `playwright_watchdog.py` | Core service |
| `injectors/pw_injector.js` | Node.js CDP injector |
| `injectors/pw_py_inject/sitecustomize.py` | Python CDP injector |
| `bin/pw-run.sh` | Node.js test wrapper |
| `bin/pw-run-pytest.sh` | Python test wrapper |
| `install.sh` | Automated installer |
| `smoke_test.sh` | Validation script |

## Documentation

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - 5-minute quickstart
- **[README.md](README.md)** - Overview & features
- **[INSTALL.md](INSTALL.md)** - Installation methods
- **[WATCHDOG_USAGE.md](WATCHDOG_USAGE.md)** - Complete guide
- **[test_validation.md](test_validation.md)** - Test scenarios
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Architecture

## Common Workflows

### Debug Specific Test
```bash
# Terminal 1: watchdog with console output
PW_WATCHDOG_STDOUT=1 ./playwright_watchdog.py

# Terminal 2: run test
./bin/pw-run.sh --grep "my-flaky-test"

# On failure: browser stays open, check CDP URL in console
```

### Collect Artifacts from CI
```bash
# After test run
jq -r '.artifacts | to_entries[] | .value[]' \
  ~/.pw_watchdog/logs/watchdog.jsonl | \
  xargs -I {} cp {} /artifacts/
```

### Monitor Long Test Suite
```bash
# Start watchdog
./playwright_watchdog.py &

# Run tests
./bin/pw-run.sh

# In another terminal, watch progress
watch -n 1 'tail -5 ~/.pw_watchdog/logs/watchdog.jsonl | jq -r ".event"'
```

---

**For more details, see [GETTING_STARTED.md](GETTING_STARTED.md)**


