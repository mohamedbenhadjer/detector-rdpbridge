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

## Quick Persistent Setup

**Goal:** Set up environment variables once so they work automatically in every new terminal and after system restarts—no need to re-run setup scripts manually.

### Linux/macOS (bash/zsh)

Add this line to your shell profile (`~/.bashrc` or `~/.zshrc`):

```bash
source /absolute/path/to/detector-rdpbridge/setup_env.sh
```

Or copy all the `export` lines from `setup_env.sh` directly into your profile. After restarting your terminal (or running `source ~/.bashrc`), the environment will be configured automatically.

### Windows PowerShell

Add this line to your PowerShell profile (`$PROFILE`):

```powershell
. "C:\absolute\path\to\detector-rdpbridge\setup_env.ps1"
```

To edit your profile: `notepad $PROFILE` (create it if it doesn't exist). After restarting PowerShell, environment variables will be set automatically.

### Windows CMD

Run the setup script once with the `install` argument to make environment variables permanent:

```cmd
setup_env.bat install
```

This uses `setx` to write variables to your user environment. They'll persist across all future CMD sessions and reboots. (Note: You'll need to open a new CMD window after installation for changes to take effect.)

---

**That's it!** Once you've completed the setup for your OS, you never need to run the setup scripts again. Jump to the detailed [Setup](#setup) section below if you need more configuration options.

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

### 2. Set Environment Variables (Persistent Setup - Recommended)

**For the simplest setup, see [Quick Persistent Setup](#quick-persistent-setup) above.**

These instructions show you how to configure environment variables so they persist across terminal sessions and reboots. Choose the method for your operating system:

#### Linux/macOS (bash/zsh) - Permanent Setup

**Option A: Source the provided script from your shell profile (Recommended)**

Add this single line to `~/.bashrc` or `~/.zshrc`:

```bash
source /absolute/path/to/detector-rdpbridge/setup_env.sh
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

**Option B: Copy environment variables directly to your profile**

Add these lines to `~/.bashrc` or `~/.zshrc`:

```bash
# MiniAgent configuration
export PYTHONPATH="/path/to/detector-rdpbridge:$PYTHONPATH"
export MINIAGENT_ENABLED=1
export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"
export MINIAGENT_TOKEN="change-me"
export MINIAGENT_CLIENT="python-cdp-monitor"
export MINIAGENT_COOLDOWN_SEC=0
export MINIAGENT_DEBUG_PORT=9222
export MINIAGENT_FORCE_DEBUG_PORT=1
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_TOKEN="change-me"
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_HOLD_SECS=3600
# Optional: redact URLs/titles in support requests
# export MINIAGENT_REDACT_URLS=1
```

Then reload:
```bash
source ~/.bashrc
```

**After setup:** Environment variables will be automatically available in every new terminal session.

#### Windows (PowerShell) - Permanent Setup

**Option A: Source the provided script from your PowerShell profile (Recommended)**

1. Open your PowerShell profile for editing:
   ```powershell
   notepad $PROFILE
   ```
   (If the file doesn't exist, create it when prompted)

2. Add this line to your profile:
   ```powershell
   . "C:\absolute\path\to\detector-rdpbridge\setup_env.ps1"
   ```

3. Save and restart PowerShell.

**Option B: Copy environment variables directly to your profile**

Add these lines to your PowerShell profile (`$PROFILE`):

```powershell
# MiniAgent configuration
$env:PYTHONPATH = "C:\path\to\detector-rdpbridge;$env:PYTHONPATH"
$env:MINIAGENT_ENABLED = "1"
$env:MINIAGENT_WS_URL = "ws://127.0.0.1:8777/ws"
$env:MINIAGENT_TOKEN = "change-me"
$env:MINIAGENT_CLIENT = "python-cdp-monitor"
$env:MINIAGENT_COOLDOWN_SEC = "0"
$env:MINIAGENT_DEBUG_PORT = "9222"
$env:MINIAGENT_FORCE_DEBUG_PORT = "1"
$env:MINIAGENT_ON_ERROR = "hold"
$env:MINIAGENT_RESUME_HTTP = "1"
$env:MINIAGENT_RESUME_HTTP_TOKEN = "change-me"
$env:MINIAGENT_RESUME_FILE = "$env:TEMP\miniagent_resume"
$env:MINIAGENT_HOLD_SECS = "3600"
```

**Option C: Set system/user environment variables via GUI**

Set permanent environment variables via System Properties → Advanced → Environment Variables. This survives reboots but requires manual entry of each variable.

**After setup:** Environment variables will be automatically available in every new PowerShell session.

#### Windows (CMD) - Permanent Setup

**Option A: Use the provided script with install mode (Recommended)**

Run once to permanently set environment variables for your user account:

```cmd
setup_env.bat install
```

After running, close and reopen CMD windows. Variables will persist across all future CMD sessions and reboots.

**Option B: Manually use setx for permanent variables**

Run these commands once (note: requires opening a new CMD window after to see changes):

```cmd
setx PYTHONPATH "C:\path\to\detector-rdpbridge;%PYTHONPATH%"
setx MINIAGENT_ENABLED "1"
setx MINIAGENT_WS_URL "ws://127.0.0.1:8777/ws"
setx MINIAGENT_TOKEN "your-token-here"
setx MINIAGENT_CLIENT "python-cdp-monitor"
setx MINIAGENT_COOLDOWN_SEC "0"
setx MINIAGENT_DEBUG_PORT "9222"
setx MINIAGENT_FORCE_DEBUG_PORT "1"
setx MINIAGENT_ON_ERROR "hold"
setx MINIAGENT_RESUME_HTTP "1"
setx MINIAGENT_RESUME_HTTP_TOKEN "your-token-here"
setx MINIAGENT_RESUME_FILE "%TEMP%\miniagent_resume"
setx MINIAGENT_HOLD_SECS "3600"
```

**Option C: Temporary setup (per-session only)**

If you prefer to set variables only for the current CMD session (not persistent), you can use `setup_env.bat` without arguments or use `set` commands instead of `setx`.

**After setup:** Environment variables will be automatically available in every new CMD session.

### 3. Get Your Shared Token

The `MINIAGENT_TOKEN` must match the token configured in your Flutter app's local WebSocket server.

You can find or generate it in your Flutter app configuration.

### 4. Run Your Tests (No Changes!)

Once you've completed the persistent setup above, simply run your Playwright tests as normal:

```bash
python my_playwright.py
```

**No need to run setup scripts or set environment variables manually—they're already configured!**

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
    "detection": {
      "successSelector": "button:has-text('Login')",
      "failureSelector": ".error-message"
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

### Detection Selectors

The `detection` object helps the RDP Host autonomously determine if a human operator successfully resolved the issue:

- **`successSelector`**: CSS selector for the element that indicates successful completion. For auto-hooked Playwright errors, this is typically derived from the failing selector (e.g., the button the script was trying to click). The RDP Host watches for this element to appear, confirming the operator completed the task.

- **`failureSelector`** (optional): CSS selector for a known error element (e.g., `.error-message`, `#login-failed-toast`). If this element appears, the RDP Host knows the operator's attempt failed. This field may be omitted when no specific error indicator is known.

For auto-hooked errors, the `successSelector` is automatically extracted from the Playwright method call (e.g., `page.click("button#submit")` → `successSelector: "button#submit"`). When triggering support requests manually via the API, you can provide custom selectors.

**For Human Agents:**
The error `description` field will include `| successSelector=<value>` so you can immediately see what element needs to appear on the page. Your job is to perform actions in the browser that make that selector become visible/present. Once the RDP Host detects the selector, the session is marked as successful.

Example: If you see `| successSelector=text=Agent Success` in the error description:
- Type "Agent Success" in a search box and submit
- The text appears on the page
- RDP Host detects it and marks the task as complete

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


