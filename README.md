# Playwright Auto-Hook Support Request Agent

Automatically detect Playwright errors and send support requests to your Flutter app **without modifying your Playwright scripts**.

## Features

- ✅ **Zero code changes** to your Playwright tests
- ✅ Catches timeouts, selector errors, actionability failures, navigation errors, assertions
- ✅ Keeps browser and process running after errors
- ✅ Auto-enables remote debugging for Chromium (allows agent control via CDP)
- ✅ Cross-browser: Chromium, Firefox, WebKit
- ✅ Cross-platform: Linux and Windows
- ✅ Deduplication and cooldown to avoid spam

## How It Works

1. Python auto-loads `sitecustomize.py` from `PYTHONPATH`
2. The hook monkey-patches Playwright APIs to intercept exceptions
3. On error, sends a WebSocket message to your Flutter app at `ws://127.0.0.1:8777/ws`
4. Flutter creates a support request with control info for remote assistance
5. Your test continues or handles the exception based on the configured mode

## Error Handling Modes

Choose how errors are handled:

### Report Mode (Default)
- Sends support request
- Re-raises the exception
- Script exits or handles error in try/except
- **Use when:** You want error reporting without changing script behavior

### Hold Mode (Recommended for Agent Intervention)
- Sends support request
- Pauses the script execution
- Keeps browser open
- Waits for agent to fix the issue
- Resumes when: `touch $MINIAGENT_RESUME_FILE` or timeout reached
- Alternatively resume via HTTP endpoint (see below)
- **Use when:** You need live agent assistance to fix errors

```bash
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_HOLD_SECS=3600  # Optional: timeout after 1 hour
```

### Swallow Mode
- Sends support request
- Returns `None` for failed action
- Script continues immediately
- **Use when:** You want to log errors but continue execution regardless

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install
```

### 2. Set Environment Variables

#### Linux (bash/zsh)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# MiniAgent configuration
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
export MINIAGENT_ENABLED=1
export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"
export MINIAGENT_TOKEN="your-shared-token-here"
export MINIAGENT_CLIENT="python-cdp-monitor"
export MINIAGENT_COOLDOWN_SEC=20
# Optional: redact URLs/titles in support requests
# export MINIAGENT_REDACT_URLS=1
```

Then reload:
```bash
source ~/.bashrc
```

#### Windows (PowerShell)

Add to your PowerShell profile (`$PROFILE`):

```powershell
# MiniAgent configuration
$env:PYTHONPATH = "C:\Users\YourUser\detector-rdpbridge;$env:PYTHONPATH"
$env:MINIAGENT_ENABLED = "1"
$env:MINIAGENT_WS_URL = "ws://127.0.0.1:8777/ws"
$env:MINIAGENT_TOKEN = "your-shared-token-here"
$env:MINIAGENT_CLIENT = "python-cdp-monitor"
$env:MINIAGENT_COOLDOWN_SEC = "20"
```

Or set system/user environment variables via System Properties → Advanced → Environment Variables.

#### Windows (CMD)

Create a batch file to set variables before running tests:

```batch
@echo off
set PYTHONPATH=C:\Users\YourUser\detector-rdpbridge;%PYTHONPATH%
set MINIAGENT_ENABLED=1
set MINIAGENT_WS_URL=ws://127.0.0.1:8777/ws
set MINIAGENT_TOKEN=your-shared-token-here
set MINIAGENT_CLIENT=python-cdp-monitor
set MINIAGENT_COOLDOWN_SEC=20

REM Run your test
python my_playwright.py
```

### 3. Get Your Shared Token

The `MINIAGENT_TOKEN` must match the token configured in your Flutter app's local WebSocket server.

You can find or generate it in your Flutter app configuration.

### 4. Run Your Tests (No Changes!)

```bash
python my_playwright.py
```

The hook will automatically:
- Intercept errors
- Enable remote debugging for Chromium
- Send support requests to Flutter

## Configuration Reference

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `PYTHONPATH` | ✅ Yes | - | Must include this directory |
| `MINIAGENT_ENABLED` | No | `1` | Set to `0` to disable the hook |
| `MINIAGENT_WS_URL` | No | `ws://127.0.0.1:8777/ws` | Flutter WebSocket server URL |
| `MINIAGENT_TOKEN` | ✅ Yes | - | Shared authentication token |
| `MINIAGENT_CLIENT` | No | `python-cdp-monitor` | Client name sent in handshake |
| `MINIAGENT_COOLDOWN_SEC` | No | `20` | Seconds between duplicate requests |
| `MINIAGENT_REDACT_URLS` | No | `0` | Set to `1` to exclude URLs/titles |
| `MINIAGENT_DEBUG_PORT` | No | `9222` | Remote debugging port for Chromium CDP |
| `MINIAGENT_FORCE_DEBUG_PORT` | No | `1` | Set to `0` to respect user-provided debug port args |
| `MINIAGENT_ON_ERROR` | No | `report` | Error handling: `report` (re-raise), `hold` (pause and wait), `swallow` (continue) |
| `MINIAGENT_RESUME_FILE` | No | `/tmp/miniagent_resume` | File path to signal resume in hold mode |
| `MINIAGENT_HOLD_SECS` | No | `""` (forever) | Timeout in seconds for hold mode, or "forever"/"inf" |
| `MINIAGENT_RESUME_HTTP` | No | `0` | Set to `1` to enable local HTTP resume endpoint |
| `MINIAGENT_RESUME_HTTP_HOST` | No | `127.0.0.1` | Host/interface to bind the HTTP endpoint |
| `MINIAGENT_RESUME_HTTP_PORT` | No | `8787` | Port for the HTTP resume endpoint |
| `MINIAGENT_RESUME_HTTP_TOKEN` | Recommended | - | Bearer token required to authorize resume requests |

## HTTP Resume Endpoint (Optional)

Instead of touching the resume file, you can trigger resume via a local HTTP endpoint. This is useful when your agent finishes a session and wants to resume the script programmatically.

**Prerequisites:** Ensure `PYTHONPATH` includes this directory (required for sitecustomize to load).

Enable and configure:

```bash
# Required: PYTHONPATH must be set
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"

# Enable HTTP resume
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_HOST=127.0.0.1
export MINIAGENT_RESUME_HTTP_PORT=8787
export MINIAGENT_RESUME_HTTP_TOKEN="strong-shared-secret"
# The hold loop still watches this file; HTTP endpoint simply creates it
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
```

Agent call example:

```bash
curl -sS -X POST \
  http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer $MINIAGENT_RESUME_HTTP_TOKEN"
```

Notes:
- The server binds to localhost by default; if you expose it beyond localhost, protect it with firewall rules or tunneling.
- The endpoint is idempotent and will log each request.

## Support Request Payload

When an error occurs, the agent sends:

```json
{
  "type": "support_request",
  "payload": {
    "description": "TimeoutError: click: locator('button:has-text(\"Login\")')",
    "controlTarget": {
      "browser": "chromium",
      "debugPort": 9222,
      "urlContains": "https://example.com/login",
      "titleContains": "Login Page"
    },
    "meta": {
      "runId": "a1b2c3d4",
      "pid": 12345,
      "reason": "TimeoutError",
      "ts": "2025-10-27T12:34:56.000Z"
    }
  }
}
```

### Browser-Specific Behavior

- **Chromium/Chrome/Edge**: `debugPort` included, remote control available via CDP
- **Firefox/WebKit**: `debugPort` omitted, limited remote control

## Detected Errors

The hook catches:

- ✅ `TimeoutError` - element not found, wait timeout
- ✅ `Error` - Playwright API errors, actionability failures
- ✅ `AssertionError` - failed expect() assertions
- ✅ Navigation timeouts and failures
- ✅ Selector errors (element not visible, not enabled, etc.)

**Note:** Both `Page` method errors (e.g., `page.click()`) and `Locator` method errors (e.g., `page.locator().click()`) include full CDP criteria (`debugPort`, `urlContains`, `titleContains`) for accurate tab targeting.

## Troubleshooting

### Hook not activating

Check that:
1. `PYTHONPATH` includes this directory
2. `MINIAGENT_TOKEN` is set
3. Playwright is installed: `pip show playwright`

Enable debug logging:
```bash
export MINIAGENT_ENABLED=1
python -c "import sitecustomize"
```

### WebSocket connection fails

1. Ensure Flutter app is running
2. Check that Flutter's local WS server is on port 8777
3. Verify token matches Flutter configuration
4. Check logs for connection errors

### No support requests sent

1. Check cooldown period (default 20s between duplicate requests)
2. Verify Flutter has a signed-in user (returns `NO_USER` error otherwise)
3. Check for `BAD_AUTH` errors (token mismatch)

### CDP not connecting to correct tab

If Flutter connects to the wrong browser window/tab:

1. Verify the error includes `debugPort`, `urlContains`, and `titleContains` in logs
2. Both Page and Locator errors should include full CDP criteria
3. If missing, check that `MINIAGENT_REDACT_URLS=1` is not set (would hide URL/title)
4. Run `tests/test_locator_error_payload.py` to verify payload structure

### Remote debugging port configuration

For Chromium, the hook automatically injects `--remote-debugging-port=9222` by default. This enables Chrome DevTools Protocol (CDP) access for remote control.

**Configuration:**
- `MINIAGENT_DEBUG_PORT=9222` (default) - Set the CDP port
- `MINIAGENT_FORCE_DEBUG_PORT=1` (default) - Override any user-provided debug port args

**Verify CDP is active:**
```bash
# Check if Chromium is listening on port 9222
curl http://127.0.0.1:9222/json/version

# Expected output:
{
   "Browser": "Chrome/...",
   "Protocol-Version": "1.3",
   "User-Agent": "Mozilla/5.0 ...",
   "WebKit-Version": "...",
   "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/..."
}
```

**Multiple concurrent browsers:**
If running multiple Chromium instances simultaneously, set `MINIAGENT_FORCE_DEBUG_PORT=0` and provide unique ports manually in your script, or use different ports via `MINIAGENT_DEBUG_PORT`.

## Testing the Setup

Create a test file `test_hook.py`:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://example.com")
    
    # This will trigger a support request (button doesn't exist)
    try:
        page.click("button:has-text('NonExistentButton')", timeout=5000)
    except Exception as e:
        print(f"Caught error: {e}")
    
    print("Test continues after error!")
    input("Press Enter to close browser...")
    browser.close()
```

Run:
```bash
python test_hook.py
```

Expected behavior:
1. Browser opens
2. After ~5s timeout, error is caught
3. Support request sent to Flutter
4. Script continues and waits for Enter

Check Flutter logs for the incoming support request.

## Uninstalling

To disable the hook:

```bash
export MINIAGENT_ENABLED=0
```

Or remove the `PYTHONPATH` entry.

## License

MIT


