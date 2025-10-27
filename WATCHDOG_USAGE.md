# Playwright Watchdog Usage Guide

## Overview

The Playwright Watchdog is a cross-platform service that monitors Playwright test runs, logs lifecycle events, keeps browsers open on failures, and provides CDP (Chrome DevTools Protocol) access for debugging and automation.

## Key Features

- **Automatic Detection**: Identifies Playwright processes (Node.js and Python)
- **Lifecycle Logging**: Logs test start/exit events as JSONL
- **CDP Access**: Enables remote debugging port and captures WebSocket URL
- **Keep Browser Open**: Integrates with `PWDEBUG=1` to preserve browser state on failures
- **No Test Modifications**: Works via environment variables and runtime injection
- **Cross-Platform**: Supports Linux and Windows

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Service (Optional)

#### Linux (systemd user service)

```bash
# Edit the service file to match your paths
vi systemd/user/pw-watchdog.service

# Copy to systemd user directory
mkdir -p ~/.config/systemd/user
cp systemd/user/pw-watchdog.service ~/.config/systemd/user/

# Enable and start
systemctl --user enable pw-watchdog
systemctl --user start pw-watchdog

# Check status
systemctl --user status pw-watchdog

# View logs
journalctl --user -u pw-watchdog -f
```

#### Windows (Scheduled Task)

```powershell
# Run the installer (adjust Python path if needed)
powershell -ExecutionPolicy Bypass -File .\windows\install_watchdog_task.ps1

# Check task status
Get-ScheduledTask -TaskName "PlaywrightWatchdog" | Get-ScheduledTaskInfo

# View logs in Event Viewer or check ~/.pw_watchdog/logs/watchdog.jsonl
```

### 3. Or Run Manually

```bash
# Run in foreground with stdout logging
PW_WATCHDOG_STDOUT=1 python3 playwright_watchdog.py

# Run in background
nohup python3 playwright_watchdog.py > /dev/null 2>&1 &
```

## Usage

### Node.js (Playwright Test)

#### Using Helper Script (Recommended)

```bash
# Make script executable
chmod +x bin/pw-run.sh

# Run tests
./bin/pw-run.sh

# With additional arguments
./bin/pw-run.sh --grep "login" --project=chromium
```

#### Manual Invocation

```bash
# Generate runId
RUNID=$(date +%s%3N)-$$
mkdir -p ~/.pw_watchdog/reports

# Set environment and run
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
PW_WATCHDOG_REPORT_FILE="$HOME/.pw_watchdog/reports/$RUNID.json" \
NODE_OPTIONS="--require $(pwd)/injectors/pw_injector.js" \
npx playwright test \
  --reporter=json,line \
  --trace=retain-on-failure
```

#### Windows PowerShell

```powershell
.\windows\pw-run.ps1

# With arguments
.\windows\pw-run.ps1 --grep "login" --project=chromium
```

### Python (pytest)

#### Using Helper Script (Recommended)

```bash
# Make script executable
chmod +x bin/pw-run-pytest.sh

# Run tests
./bin/pw-run-pytest.sh

# With additional arguments
./bin/pw-run-pytest.sh -k "test_login" --maxfail=1
```

#### Manual Invocation

```bash
# Generate runId
RUNID=$(date +%s%3N)-$$
mkdir -p ~/.pw_watchdog/reports

# Set environment and run
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
PW_WATCHDOG_REPORT_FILE="$HOME/.pw_watchdog/reports/$RUNID.xml" \
PYTHONPATH="$(pwd)/injectors/pw_py_inject" \
PYTEST_ADDOPTS="--junitxml=$HOME/.pw_watchdog/reports/$RUNID.xml" \
pytest
```

#### Windows PowerShell

```powershell
.\windows\pw-run-pytest.ps1

# With arguments
.\windows\pw-run-pytest.ps1 -k "test_login" --maxfail=1
```

## Output and Logs

### JSONL Event Log

All events are logged to `~/.pw_watchdog/logs/watchdog.jsonl` with automatic rotation.

#### Event Types

**1. playwright_started**

```json
{
  "event": "playwright_started",
  "ts": "2025-10-26T12:34:56.789Z",
  "runId": "12345-1729945696789",
  "os": "Linux",
  "pid": 12345,
  "ppid": 12340,
  "cmdline": ["npx", "playwright", "test"],
  "cwd": "/home/user/project",
  "user": "user",
  "engine": "chromium",
  "cdp": {
    "port": 9222,
    "wsUrl": "ws://127.0.0.1:9222/devtools/browser/...",
    "devtoolsActivePortPath": "/tmp/.../DevToolsActivePort"
  }
}
```

**2. playwright_succeeded**

```json
{
  "event": "playwright_succeeded",
  "ts": "2025-10-26T12:35:10.123Z",
  "runId": "12345-1729945696789",
  "pid": 12345,
  "exitCode": 0,
  "durationMs": 13334,
  "artifacts": {
    "reportFile": "/home/user/.pw_watchdog/reports/12345-1729945696789.json"
  }
}
```

**3. playwright_failed**

```json
{
  "event": "playwright_failed",
  "ts": "2025-10-26T12:35:10.123Z",
  "runId": "12345-1729945696789",
  "pid": 12345,
  "exitCode": 1,
  "durationMs": 13334,
  "error": {
    "title": "Login > should authenticate user",
    "message": "expect(received).toBe(expected)\n\nExpected: true\nReceived: false",
    "stack": "..."
  },
  "artifacts": {
    "reportFile": "/home/user/.pw_watchdog/reports/12345-1729945696789.json",
    "traces": ["/home/user/project/test-results/.../trace.zip"],
    "screenshots": ["/home/user/project/test-results/.../screenshot.png"]
  }
}
```

### CDP Metadata

CDP connection info is written to `~/.pw_watchdog/cdp/<runId>.json`:

```json
{
  "runId": "12345-1729945696789",
  "port": 9222,
  "wsUrl": "ws://127.0.0.1:9222/devtools/browser/abc123...",
  "devtoolsActivePortPath": "/tmp/playwright_chromium_12345/DevToolsActivePort",
  "timestamp": "2025-10-26T12:34:56.789Z"
}
```

## Configuration

### Environment Variables

Create a `.env` file (see `.env.example`) or set environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PW_WATCHDOG_DIR` | `~/.pw_watchdog` | Base directory for logs and metadata |
| `PW_WATCHDOG_POLL_INTERVAL` | `0.5` | Process polling interval (seconds) |
| `PW_WATCHDOG_STDOUT` | `1` | Enable stdout logging (1=yes, 0=no) |
| `PW_WATCHDOG_LOG_MAX_SIZE` | `10485760` | Max log file size (bytes) |
| `PW_WATCHDOG_LOG_BACKUPS` | `5` | Number of log backups to keep |
| `PW_WATCHDOG_USE_NETLINK` | `auto` | Linux: use netlink (requires root) |
| `PW_WATCHDOG_RUN_ID` | auto-generated | Override runId (usually not needed) |
| `PW_WATCHDOG_REPORT_FILE` | auto-detected | Path to report file |

### Runtime Directories

The watchdog creates these subdirectories under `~/.pw_watchdog/`:

- `logs/` - JSONL event logs
- `cdp/` - CDP metadata files
- `reports/` - Test report files (JSON/XML)
- `tmp/` - Temporary files

## How It Works

### 1. Process Detection

The watchdog monitors system processes and identifies Playwright runs by command-line patterns:

- **Node.js**: `node.*playwright.*test`, `npx playwright test`
- **Python**: `pytest.*playwright`, `pytest.*--browser`

### 2. Runtime Injection

#### Node.js (`pw_injector.js`)

- Loaded via `NODE_OPTIONS=--require`
- Patches `chromium.launch()` before Playwright loads
- Adds `--remote-debugging-port=0` and `headless: false`
- Discovers CDP WebSocket URL from `DevToolsActivePort`
- Writes metadata to `~/.pw_watchdog/cdp/<runId>.json`

#### Python (`sitecustomize.py`)

- Loaded via `PYTHONPATH` pointing to `injectors/pw_py_inject/`
- Monkey-patches `BrowserType.launch()` for both sync and async APIs
- Same CDP discovery and metadata writing as Node.js

### 3. Artifact Correlation

The watchdog reads report files on process exit:

- **Node.js**: Parses Playwright JSON reporter output
- **Python**: Parses pytest JUnit XML output

Extracts:
- Test failure details (title, message, stack trace)
- Artifact paths (traces, screenshots, videos)

### 4. Keep Browser Open

When `PWDEBUG=1` is set, Playwright's built-in debug mode:
- Keeps the browser open on failures
- Pauses execution with inspector active

Combined with the CDP injector, the browser remains accessible via the WebSocket URL.

## Troubleshooting

### Watchdog Not Detecting Tests

1. Check that the watchdog is running:
   ```bash
   ps aux | grep playwright_watchdog
   ```

2. Verify process patterns match your command:
   ```bash
   ps aux | grep -E 'playwright|pytest'
   ```

3. Check logs for detection attempts:
   ```bash
   tail -f ~/.pw_watchdog/logs/watchdog.jsonl
   ```

### CDP Info Not Available

1. Verify the injector is loaded:
   ```bash
   # Node.js
   echo $NODE_OPTIONS
   # Should include: --require .../pw_injector.js
   
   # Python
   echo $PYTHONPATH
   # Should include: .../pw_py_inject
   ```

2. Check injector logs (stderr):
   ```bash
   # Look for "[pw_injector]" or "[pw_py_inject]" messages
   ```

3. Ensure Chromium is the browser being used (injector only patches Chromium)

### Windows WMI Issues

If WMI fails, the watchdog falls back to polling:

1. Check Event Viewer for WMI errors
2. Ensure `pywin32` is installed: `pip install pywin32`
3. Try running as administrator if permissions are an issue

### Linux Permissions

- Polling mode requires no special permissions
- Netlink mode requires root (`sudo` or systemd with `User=root`)

## Advanced Usage

### Custom Report Paths

```bash
# Override report file location
export PW_WATCHDOG_REPORT_FILE="/custom/path/report.json"
```

### Multiple Concurrent Runs

Each run gets a unique `runId`, so concurrent tests are supported:

```bash
# Terminal 1
./bin/pw-run.sh --grep "login" &

# Terminal 2
./bin/pw-run.sh --grep "checkout" &
```

### Parsing JSONL Logs

```bash
# Extract all failed runs
jq -r 'select(.event == "playwright_failed")' ~/.pw_watchdog/logs/watchdog.jsonl

# Get CDP WebSocket URLs
jq -r 'select(.event == "playwright_started") | .cdp.wsUrl' ~/.pw_watchdog/logs/watchdog.jsonl

# Summary of today's runs
jq -r 'select(.ts | startswith("2025-10-26")) | {event, runId, exitCode}' \
  ~/.pw_watchdog/logs/watchdog.jsonl
```

### Connecting to CDP

Once you have the WebSocket URL from the logs:

```javascript
// Node.js example
const CDP = require('chrome-remote-interface');

const wsUrl = 'ws://127.0.0.1:9222/devtools/browser/...';
const client = await CDP({ target: wsUrl });

const { Page, Runtime } = client;
await Page.enable();
await Runtime.enable();

// Take screenshot
const screenshot = await Page.captureScreenshot();
// ... etc
```

```python
# Python example
import asyncio
from playwright.async_api import async_playwright

async def connect_to_cdp():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('ws://127.0.0.1:9222/devtools/browser/...')
        page = browser.contexts[0].pages[0]
        
        await page.screenshot(path='debug.png')
        # ... etc
```

## Security Considerations

- The watchdog runs with the same privileges as the user
- CDP exposes full browser control; only use on trusted networks
- Log files may contain sensitive test data; protect `~/.pw_watchdog/`
- Scheduled task/service should not run as elevated user unless necessary

## Contributing

Contributions welcome! Areas for improvement:

- Full netlink support for Linux (currently falls back to polling)
- Additional browser support (Firefox, WebKit)
- Integration with CI/CD platforms
- Web dashboard for viewing logs
- Real-time notifications (webhooks, Slack, etc.)

## License

[Your license here]


