# Getting Started with Playwright Watchdog

This guide will get you up and running with the Playwright Watchdog in just a few minutes.

## Quick Start (5 Minutes)

### 1. Install Dependencies

Choose the method that works for your system:

**Option A: Virtual Environment (Recommended)**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Option B: System Packages (Debian/Ubuntu)**
```bash
sudo apt update
sudo apt install python3-psutil python3-dotenv
```

**Option C: User Install**
```bash
pip install --user psutil python-dotenv
```

### 2. Start the Watchdog

```bash
./playwright_watchdog.py
```

Leave this running in a terminal. You should see initialization messages.

### 3. Run a Test

**Node.js Project:**
```bash
# In another terminal
cd /path/to/your/playwright/project
/path/to/detector-rdpbridge/bin/pw-run.sh
```

**Python Project:**
```bash
cd /path/to/your/pytest/project
/path/to/detector-rdpbridge/bin/pw-run-pytest.sh
```

### 4. Check the Logs

```bash
# View real-time events
tail -f ~/.pw_watchdog/logs/watchdog.jsonl

# Pretty print with jq
tail -f ~/.pw_watchdog/logs/watchdog.jsonl | jq .

# View CDP metadata
cat ~/.pw_watchdog/cdp/*.json
```

## What You'll See

When you run a test, you'll see events like:

**Test Start:**
```json
{
  "event": "playwright_started",
  "ts": "2025-10-26T12:34:56.789Z",
  "runId": "12345-1729945696789",
  "pid": 12345,
  "cmdline": ["npx", "playwright", "test"],
  "engine": "chromium",
  "cdp": {
    "port": 9222,
    "wsUrl": "ws://127.0.0.1:9222/devtools/browser/abc123"
  }
}
```

**Test Failure (if test fails):**
```json
{
  "event": "playwright_failed",
  "ts": "2025-10-26T12:35:10.123Z",
  "runId": "12345-1729945696789",
  "exitCode": 1,
  "error": {
    "title": "Login test",
    "message": "Expected true, got false"
  },
  "artifacts": {
    "traces": ["test-results/trace.zip"],
    "screenshots": ["test-results/screenshot.png"]
  }
}
```

**Browser Stays Open:** When a test fails, the browser window will remain open for inspection, and you can connect to it via the CDP WebSocket URL!

## Common Scenarios

### Scenario 1: Debug a Flaky Test

```bash
# Terminal 1: Start watchdog
./playwright_watchdog.py

# Terminal 2: Run test repeatedly
for i in {1..10}; do
  ./bin/pw-run.sh --grep "flaky-test"
done

# Terminal 3: Watch for failures
tail -f ~/.pw_watchdog/logs/watchdog.jsonl | jq 'select(.event == "playwright_failed")'
```

When a failure occurs:
- Browser stays open at the failure point
- CDP URL is available in the logs
- Trace and screenshots are captured
- You can connect programmatically to the browser

### Scenario 2: Connect to CDP from Your Code

Get the WebSocket URL from the logs:

```bash
# Get the most recent CDP URL
jq -r 'select(.event == "playwright_started") | .cdp.wsUrl' \
  ~/.pw_watchdog/logs/watchdog.jsonl | tail -1
```

Then connect from Node.js:

```javascript
const CDP = require('chrome-remote-interface');

const wsUrl = 'ws://127.0.0.1:9222/devtools/browser/...';
const client = await CDP({ target: wsUrl });

const { Page, Runtime } = client;
await Page.enable();
await Runtime.enable();

// Take additional screenshots
const screenshot = await Page.captureScreenshot();
// Evaluate JavaScript
const result = await Runtime.evaluate({ expression: 'document.title' });
```

Or from Python:

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.connect_over_cdp('ws://127.0.0.1:9222/...')
    page = browser.contexts[0].pages[0]
    await page.screenshot(path='debug.png')
```

### Scenario 3: CI/CD Integration

Parse the logs for automated reporting:

```bash
# Count failures in last run
jq 'select(.event == "playwright_failed")' ~/.pw_watchdog/logs/watchdog.jsonl | wc -l

# Get failure details
jq -r 'select(.event == "playwright_failed") | 
  "\(.runId): \(.error.title) - \(.error.message)"' \
  ~/.pw_watchdog/logs/watchdog.jsonl

# Extract artifact paths for archival
jq -r 'select(.artifacts.traces) | .artifacts.traces[]' \
  ~/.pw_watchdog/logs/watchdog.jsonl
```

## Installation as a Service

For production use, install as a background service:

**Linux:**
```bash
./install.sh
# Follow prompts to install systemd service

# Manage the service
systemctl --user start pw-watchdog
systemctl --user stop pw-watchdog
systemctl --user status pw-watchdog
```

**Windows:**
```powershell
.\windows\install_watchdog_task.ps1
# Follow prompts

# Manage the task
Start-ScheduledTask -TaskName "PlaywrightWatchdog"
Stop-ScheduledTask -TaskName "PlaywrightWatchdog"
Get-ScheduledTask -TaskName "PlaywrightWatchdog" | Get-ScheduledTaskInfo
```

## Configuration

Create or edit `.env` to customize:

```bash
# Where logs and metadata are stored
PW_WATCHDOG_DIR=/custom/path/.pw_watchdog

# How often to check for new processes (seconds)
PW_WATCHDOG_POLL_INTERVAL=0.5

# Log to console in addition to file
PW_WATCHDOG_STDOUT=1

# Log rotation settings
PW_WATCHDOG_LOG_MAX_SIZE=10485760  # 10MB
PW_WATCHDOG_LOG_BACKUPS=5
```

## Troubleshooting

### "Module not found: psutil"

Install dependencies:
```bash
pip install -r requirements.txt
# or
sudo apt install python3-psutil
```

### "externally-managed-environment"

Use a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Watchdog Not Detecting Tests

1. Check it's running: `ps aux | grep playwright_watchdog`
2. Verify your test command matches detection patterns
3. Check logs: `tail -f ~/.pw_watchdog/logs/watchdog.jsonl`

### No CDP Information

1. Verify injector is loaded:
   - Node.js: `echo $NODE_OPTIONS` should show `--require .../pw_injector.js`
   - Python: `echo $PYTHONPATH` should show `.../pw_py_inject`

2. Use the helper scripts (they set this up automatically):
   ```bash
   ./bin/pw-run.sh
   ./bin/pw-run-pytest.sh
   ```

3. Check that you're using Chromium (CDP only works with Chromium)

## Next Steps

1. **Read the full documentation:**
   - [README.md](README.md) - Overview and features
   - [INSTALL.md](INSTALL.md) - Detailed installation options
   - [WATCHDOG_USAGE.md](WATCHDOG_USAGE.md) - Complete usage guide

2. **Run the smoke test:**
   ```bash
   ./smoke_test.sh
   ```

3. **Try the validation tests:**
   See [test_validation.md](test_validation.md) for comprehensive test scenarios

4. **Integrate with your CI/CD:**
   Add the watchdog to your CI pipeline to track test failures and capture artifacts

## Tips

- **Multiple Runs:** Each run gets a unique `runId`, so you can run tests concurrently
- **Custom runId:** Set `PW_WATCHDOG_RUN_ID=my-custom-id` to use a specific identifier
- **Querying Logs:** Use `jq` to filter and analyze JSONL logs
- **Cleanup:** Old CDP metadata files are automatically removed after 24 hours
- **Performance:** The watchdog adds <1% overhead to test execution

## Example Workflow

```bash
# 1. Start watchdog (one time, or as service)
./playwright_watchdog.py &

# 2. Run your tests throughout the day
./bin/pw-run.sh --grep "smoke"
./bin/pw-run.sh --grep "regression"
./bin/pw-run.sh  # all tests

# 3. At end of day, analyze results
echo "Total runs:"
jq -s 'length' ~/.pw_watchdog/logs/watchdog.jsonl

echo "Failures today:"
jq -r 'select(.event == "playwright_failed" and .ts > "2025-10-26")' \
  ~/.pw_watchdog/logs/watchdog.jsonl | jq -s 'length'

echo "Average test duration:"
jq -s 'map(select(.durationMs)) | add/length' \
  ~/.pw_watchdog/logs/watchdog.jsonl
```

## Support

- Detailed docs: [WATCHDOG_USAGE.md](WATCHDOG_USAGE.md)
- Installation help: [INSTALL.md](INSTALL.md)
- Implementation details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Test scenarios: [test_validation.md](test_validation.md)

---

**You're all set!** Start the watchdog and run your tests. Happy debugging! 🎭🐛


