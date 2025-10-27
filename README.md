# Playwright Watchdog with CDP Support

A cross-platform service that monitors Playwright test runs, logs lifecycle events, keeps browsers open on failures, and provides Chrome DevTools Protocol (CDP) access for debugging and automation — all without modifying test code.

## Features

- 🔍 **Automatic Detection**: Identifies Playwright processes (Node.js and Python)
- 📊 **Lifecycle Logging**: Logs test start/exit events as structured JSONL
- 🐛 **CDP Access**: Enables remote debugging and captures WebSocket URLs
- 🌐 **Keep Browser Open**: Preserves browser state on failures for debugging
- 🚫 **No Test Modifications**: Works via environment variables and runtime injection
- 🖥️ **Cross-Platform**: Full support for Linux and Windows

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the Watchdog

#### Run Manually (foreground)

```bash
./playwright_watchdog.py
```

#### Or Install as Service

**Linux (systemd):**

```bash
# Edit paths in the service file
vi systemd/user/pw-watchdog.service

# Install
mkdir -p ~/.config/systemd/user
cp systemd/user/pw-watchdog.service ~/.config/systemd/user/
systemctl --user enable --now pw-watchdog

# Check status
systemctl --user status pw-watchdog
```

**Windows (Scheduled Task):**

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\install_watchdog_task.ps1
```

### 3. Run Your Tests

#### Node.js (Playwright Test)

```bash
./bin/pw-run.sh

# Or manually:
RUNID=$(date +%s%3N)-$$
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
NODE_OPTIONS="--require $(pwd)/injectors/pw_injector.js" \
npx playwright test --reporter=json,line --trace=retain-on-failure
```

#### Python (pytest)

```bash
./bin/pw-run-pytest.sh

# Or manually:
RUNID=$(date +%s%3N)-$$
PWDEBUG=1 \
PW_WATCHDOG_RUN_ID="$RUNID" \
PYTHONPATH="$(pwd)/injectors/pw_py_inject" \
PYTEST_ADDOPTS="--junitxml=$HOME/.pw_watchdog/reports/$RUNID.xml" \
pytest
```

## How It Works

### Architecture

1. **Watchdog Core** (`playwright_watchdog.py`)
   - Monitors system processes for Playwright test runs
   - Uses WMI on Windows, psutil polling on Linux (with optional netlink support)
   - Logs structured events as JSONL

2. **Runtime Injectors** (no test code changes)
   - **Node.js** (`injectors/pw_injector.js`): Patches `chromium.launch()` via `NODE_OPTIONS`
   - **Python** (`injectors/pw_py_inject/sitecustomize.py`): Monkey-patches `BrowserType.launch()` via `PYTHONPATH`
   - Both force `--remote-debugging-port=0` and `headless: false` for Chromium

3. **Artifact Correlation**
   - Parses Playwright JSON reports (Node.js) or JUnit XML (Python)
   - Extracts failure details, trace files, screenshots
   - Correlates with process lifecycle events

4. **CDP Metadata**
   - Injectors discover the CDP WebSocket URL from `DevToolsActivePort`
   - Written to `~/.pw_watchdog/cdp/<runId>.json`
   - Available for programmatic browser control

## Output

### Event Log (`~/.pw_watchdog/logs/watchdog.jsonl`)

**playwright_started:**
```json
{
  "event": "playwright_started",
  "ts": "2025-10-26T12:34:56.789Z",
  "runId": "12345-1729945696789",
  "os": "Linux",
  "pid": 12345,
  "cmdline": ["npx", "playwright", "test"],
  "engine": "chromium",
  "cdp": {
    "port": 9222,
    "wsUrl": "ws://127.0.0.1:9222/devtools/browser/..."
  }
}
```

**playwright_failed:**
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
    "message": "Expected: true, Received: false"
  },
  "artifacts": {
    "traces": ["test-results/.../trace.zip"],
    "screenshots": ["test-results/.../screenshot.png"]
  }
}
```

### CDP Metadata (`~/.pw_watchdog/cdp/<runId>.json`)

```json
{
  "runId": "12345-1729945696789",
  "port": 9222,
  "wsUrl": "ws://127.0.0.1:9222/devtools/browser/abc123...",
  "devtoolsActivePortPath": "/tmp/playwright_chromium_12345/DevToolsActivePort"
}
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# Watchdog directory (default: ~/.pw_watchdog)
PW_WATCHDOG_DIR=/custom/path

# Poll interval in seconds (default: 0.5)
PW_WATCHDOG_POLL_INTERVAL=0.5

# Enable stdout logging (default: 1)
PW_WATCHDOG_STDOUT=1

# Log rotation (default: 10MB, 5 backups)
PW_WATCHDOG_LOG_MAX_SIZE=10485760
PW_WATCHDOG_LOG_BACKUPS=5
```

See `.env.example` for all options.

## Project Structure

```
.
├── playwright_watchdog.py          # Core watchdog service
├── injectors/
│   ├── pw_injector.js             # Node.js runtime injector
│   └── pw_py_inject/
│       └── sitecustomize.py       # Python runtime injector
├── bin/
│   ├── pw-run.sh                  # Node.js test wrapper (Linux/macOS)
│   └── pw-run-pytest.sh           # Python test wrapper (Linux/macOS)
├── windows/
│   ├── install_watchdog_task.ps1  # Service installer
│   ├── pw-run.ps1                 # Node.js test wrapper
│   └── pw-run-pytest.ps1          # Python test wrapper
├── systemd/
│   └── user/
│       └── pw-watchdog.service    # systemd unit file
├── requirements.txt               # Python dependencies
├── WATCHDOG_USAGE.md             # Detailed usage guide
└── README.md                      # This file
```

## Use Cases

### 1. Debugging Flaky Tests

When a test fails, the browser stays open with `PWDEBUG=1`, and you have:
- Visual inspection of the final state
- CDP WebSocket URL for programmatic control
- Trace files and screenshots in the logs

### 2. CI/CD Integration

Parse the JSONL logs for:
- Test duration metrics
- Failure summaries with stack traces
- Artifact locations for archival

### 3. Remote Browser Automation

Use the CDP WebSocket URL to:
- Take additional screenshots
- Execute custom DevTools commands
- Inject debugging scripts
- Control the browser programmatically

### 4. Monitoring Production Smoke Tests

Run the watchdog on a schedule to:
- Track test health over time
- Correlate failures with deployments
- Alert on persistent issues

## Advanced Usage

### Connect to CDP Programmatically

**Node.js:**
```javascript
const CDP = require('chrome-remote-interface');

const wsUrl = 'ws://127.0.0.1:9222/devtools/browser/...';
const client = await CDP({ target: wsUrl });

const { Page } = client;
await Page.enable();
await Page.captureScreenshot({ path: 'debug.png' });
```

**Python:**
```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp('ws://...')
    page = browser.contexts[0].pages[0]
    await page.screenshot(path='debug.png')
```

### Query JSONL Logs

```bash
# Find all failures
jq 'select(.event == "playwright_failed")' ~/.pw_watchdog/logs/watchdog.jsonl

# Extract CDP URLs
jq -r 'select(.event == "playwright_started") | .cdp.wsUrl' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Summary stats
jq -s 'group_by(.event) | map({event: .[0].event, count: length})' \
  ~/.pw_watchdog/logs/watchdog.jsonl
```

## Troubleshooting

### Watchdog not detecting tests

1. Ensure the watchdog is running: `ps aux | grep playwright_watchdog`
2. Check command patterns match: Review `NODE_PATTERNS` and `PYTHON_PATTERNS` in the code
3. Tail logs: `tail -f ~/.pw_watchdog/logs/watchdog.jsonl`

### CDP info not available

1. Verify injector is loaded: `echo $NODE_OPTIONS` or `echo $PYTHONPATH`
2. Look for injector stderr messages: `[pw_injector]` or `[pw_py_inject]`
3. Confirm Chromium is being used (injectors only patch Chromium)

### Performance impact

- Polling mode: ~0.5s interval, minimal CPU (~0.1%)
- WMI (Windows): Event-driven, near-zero overhead
- Netlink (Linux): Event-driven but requires root

## Documentation

See [WATCHDOG_USAGE.md](WATCHDOG_USAGE.md) for comprehensive documentation including:
- Detailed installation steps
- Platform-specific configuration
- Complete API reference
- Security considerations
- Troubleshooting guide

## Requirements

- Python 3.7+
- `psutil` for process monitoring
- `python-dotenv` for configuration
- `pywin32` (Windows only, for WMI)
- Playwright (Node.js or Python) for your tests

## Contributing

Contributions welcome! Areas for improvement:
- Full netlink implementation for Linux
- Firefox and WebKit support
- Web dashboard for log visualization
- Webhook notifications
- Integration tests

## License

MIT License - see LICENSE file for details

---

**Note**: This watchdog is designed for development and CI environments. CDP exposes full browser control, so use on trusted networks only.


