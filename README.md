# Playwright Auto-Hook Support Request Agent

Automatically detect Playwright errors and send support requests to your Flutter app **without modifying your Playwright scripts**.

## Features

- ✅ **Explicit Agent Handoff**: Triggers support requests specifically when `NeedsAgentInterventionError` is raised
- ✅ **Automatic Context Capture**: Captures full browser state (CDP target, debug port, URL) even for manually raised errors
- ✅ **Global Selector Tracking**: Automatically inherits selectors from the last failed Playwright action
- ✅ **Hold & Fix**: Keeps browser open and pauses script execution for agent intervention
- ✅ **Auto-Resume**: Resumes script execution automatically after agent fixes the issue
- ✅ **Zero Config CDP**: Auto-enables remote debugging for Chromium with dynamic port allocation
- ✅ **Popup Prevention**: Keeps agent focused on a single tab by preventing new windows
- ✅ **Cross-Platform**: Works on Linux, macOS, and Windows

## How It Works

1. Python auto-loads `sitecustomize.py` from `PYTHONPATH` when your script starts
2. The hook monkey-patches Playwright APIs (`Page`, `Locator`, `Browser`, `BrowserContext`) to intercept exceptions and inject CDP/popup-prevention settings
3. For Chromium browsers, automatically injects `--remote-debugging-port` with dynamic port allocation
4. Installs popup/new-tab prevention on all browser contexts and pages (can be disabled)
5. On `NeedsAgentInterventionError`, extracts page context, CDP target ID, and inherits detection selectors from the last failure
6. Sends a WebSocket message to your Flutter app at `ws://127.0.0.1:8777/ws` with full control metadata
7. Flutter creates a support request with `controlTarget` (browser, debugPort, targetId, URL) and `detection` (successSelector, failureSelector)
8. Optionally starts HTTP resume endpoint for programmatic script resumption
9. Your test continues or handles the exception based on the configured mode (`report`, `hold`, `swallow`)

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
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume  # Auto-suffixed with PID: /tmp/miniagent_resume_12345
export MINIAGENT_HOLD_SECS=3600  # Optional: timeout after 1 hour (default: forever)
```

**Note:** The resume file path is automatically suffixed with the process ID (e.g., `/tmp/miniagent_resume_12345`) to allow multiple processes to run concurrently. The exact path is included in the support request's `meta` section (check logs) or `resumeEndpoint` when HTTP resume is enabled.

### Swallow Mode
- Sends support request
- Returns `None` for failed action
- Script continues immediately
- **Use when:** You want to log errors but continue execution regardless

## Popup / New-Tab Prevention

By default, the hook prevents new browser tabs and popups from opening to keep agent interactions focused on a single tab. This works for both sync and async Playwright on Chromium, Firefox, and WebKit.

**How it works:**
- Injects JavaScript to override `window.open()` and intercept links with `target="_blank"`
- Automatically redirects popup/new-tab navigation to the same tab
- Closes any popups that still manage to open
- Applied automatically to all pages via `Browser.new_context()`, `Browser.new_page()`, `BrowserContext.new_page()`, and persistent contexts

**Configuration:**

```bash
# Disable popup prevention entirely
export MINIAGENT_PREVENT_NEW_TABS=0

# Allow specific URLs to open in new tabs (comma-separated regex patterns)
export MINIAGENT_ALLOW_NEW_TAB_REGEX="google\.com/maps,.*download.*"

# Enable verbose logging of popup prevention actions
export MINIAGENT_PREVENT_TABS_LOG=1
```

**Important for test authors:**
- If your tests rely on real new-window behavior (e.g., testing multi-window flows), disable this feature or use the allowlist.
- OAuth flows and file downloads may trigger popups; add patterns to the allowlist if needed.
- The prevention applies globally to all browser instances launched in the same process.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install
```

### 2. Set Environment Variables (Persistent Setup - Recommended)

**For the simplest setup, see [Quick Persistent Setup](#quick-persistent-setup) above.**

**Note about defaults vs recommended values:**
- The code has built-in defaults (e.g., `MINIAGENT_COOLDOWN_SEC=0`, `MINIAGENT_ON_ERROR=report`, `MINIAGENT_FORCE_DEBUG_PORT=1`)
- The provided setup scripts (`setup_env.sh`, `setup_env.ps1`, `setup_env.bat`) contain **recommended values** optimized for agent intervention workflows
- Specifically, the scripts set `MINIAGENT_ON_ERROR=hold` and enable HTTP resume by default, which differs from code defaults but is more useful for live agent assistance
- You can source the scripts as-is for the recommended configuration, or customize individual variables as needed

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
export MINIAGENT_FORCE_DEBUG_PORT=0
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_TOKEN="change-me"
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_HOLD_SECS=3600
# Optional: redact URLs/titles in support requests
# export MINIAGENT_REDACT_URLS=1
# Optional: popup/tab prevention (enabled by default)
# export MINIAGENT_PREVENT_NEW_TABS=1
# export MINIAGENT_ALLOW_NEW_TAB_REGEX="pattern1,pattern2"
# export MINIAGENT_PREVENT_TABS_LOG=0
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
# Optional: popup/tab prevention (enabled by default)
# $env:MINIAGENT_PREVENT_NEW_TABS = "1"
# $env:MINIAGENT_ALLOW_NEW_TAB_REGEX = "pattern1,pattern2"
# $env:MINIAGENT_PREVENT_TABS_LOG = "0"
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
| `MINIAGENT_COOLDOWN_SEC` | No | `0` | Seconds between duplicate requests (0 = no cooldown) |
| `MINIAGENT_REDACT_URLS` | No | `0` | Set to `1` to exclude URLs/titles |
| `MINIAGENT_DEBUG_PORT` | No | `9222` | Base remote debugging port for Chromium CDP (auto-incremented if in use) |
| `MINIAGENT_FORCE_DEBUG_PORT` | No | `1` | Set to `0` to respect user-provided debug port args |
| `MINIAGENT_ON_ERROR` | No | `report` | Error handling: `report` (re-raise), `hold` (pause and wait), `swallow` (continue) |
| `MINIAGENT_RESUME_FILE` | No | `/tmp/miniagent_resume` (Linux/Mac) or `%TEMP%\miniagent_resume` (Windows) | File path to signal resume in hold mode; uses per-process suffix |
| `MINIAGENT_HOLD_SECS` | No | `""` (forever) | Timeout in seconds for hold mode, or "forever"/"inf" |
| `MINIAGENT_RESUME_HTTP` | No | `0` | Set to `1` to enable local HTTP resume endpoint |
| `MINIAGENT_RESUME_HTTP_HOST` | No | `127.0.0.1` | Host/interface to bind the HTTP endpoint |
| `MINIAGENT_RESUME_HTTP_PORT` | No | `8787` | Base port for HTTP resume endpoint (auto-incremented if in use) |
| `MINIAGENT_RESUME_HTTP_TOKEN` | Recommended | - | Bearer token required to authorize resume requests |
| `MINIAGENT_PREVENT_NEW_TABS` | No | `1` | Set to `0` to allow new tabs/popups (default blocks them) |
| `MINIAGENT_ALLOW_NEW_TAB_REGEX` | No | `""` | Comma-separated regex patterns for URLs allowed to open in new tabs |
| `MINIAGENT_PREVENT_TABS_LOG` | No | `0` | Set to `1` to enable verbose logging of popup prevention actions |

## HTTP Resume Endpoint (Optional)

Instead of touching the resume file, you can trigger resume via a local HTTP endpoint. This is useful when your agent finishes a session and wants to resume the script programmatically.

**How it works:**
- The HTTP server only starts when `MINIAGENT_RESUME_HTTP=1` and `MINIAGENT_RESUME_HTTP_TOKEN` is set
- Each process dynamically selects a free port starting from `MINIAGENT_RESUME_HTTP_PORT` (default: 8787)
- The actual chosen port is included in the support request payload's `resumeEndpoint` field
- When the endpoint receives a valid POST request, it creates the resume file (`MINIAGENT_RESUME_FILE`)
- The hold loop detects the file and resumes script execution

**Prerequisites:** Ensure `PYTHONPATH` includes this directory (required for sitecustomize to load).

Enable and configure:

```bash
# Required: PYTHONPATH must be set
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"

# Enable HTTP resume
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_HOST=127.0.0.1
export MINIAGENT_RESUME_HTTP_PORT=8787  # Base port; actual port auto-incremented if in use
export MINIAGENT_RESUME_HTTP_TOKEN="strong-shared-secret"
# The hold loop still watches this file; HTTP endpoint simply creates it
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
```

Agent call example (use port from `resumeEndpoint` in support request payload):

```bash
# Port 8787 is the base; check support request payload for actual port
curl -sS -X POST \
  http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer $MINIAGENT_RESUME_HTTP_TOKEN"
```

**Multi-process behavior:**
- Each process gets a unique resume file with PID suffix: `/tmp/miniagent_resume_12345`
- Each process binds to a different port (8787, 8788, 8789, etc.) to avoid conflicts
- The Flutter app receives the correct port and resume file path in each support request's `resumeEndpoint`

Notes:
- The server binds to localhost by default; if you expose it beyond localhost, protect it with firewall rules or tunneling.
- The endpoint is idempotent and will log each request.
- Resume file mechanism is still the primary signal; HTTP endpoint is a convenience wrapper.

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
      "targetId": "E4B3F...",
      "urlContains": "https://example.com/login",
      "titleContains": "Login Page",
      "resumeEndpoint": {
        "scheme": "http",
        "host": "127.0.0.1",
        "port": 8787,
        "path": "/resume",
        "token": "strong-shared-secret"
      }
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

**Field descriptions:**

- **`controlTarget.browser`**: Browser type (`chromium`, `firefox`, `webkit`)
- **`controlTarget.debugPort`**: Remote debugging port (Chromium only)
- **`controlTarget.targetId`**: CDP Target ID for the specific page/tab (Chromium only, when resolution succeeds)
- **`controlTarget.urlContains`**: Current page URL (truncated to 100 chars)
- **`controlTarget.titleContains`**: Current page title (truncated to 100 chars)
- **`controlTarget.resumeEndpoint`**: HTTP endpoint info for resuming the script (when `MINIAGENT_RESUME_HTTP=1`)
- **`detection.successSelector`**: CSS selector indicating successful completion
- **`detection.failureSelector`**: CSS selector indicating failure (optional)

### Detection Selectors

The `detection` object helps the RDP Host autonomously determine if a human operator successfully resolved the issue:

- **`successSelector`**: CSS selector for the element that indicates successful completion. For auto-hooked Playwright errors, this is typically derived from the failing selector (e.g., the button the script was trying to click). The RDP Host watches for this element to appear, confirming the operator completed the task.

- **`failureSelector`** (optional): CSS selector for a known error element (e.g., `.error-message`, `#login-failed-toast`). If this element appears, the RDP Host knows the operator's attempt failed. This field may be omitted when no specific error indicator is known.

**Wrapped Playwright Methods:**

The hook automatically wraps these methods on `Page` and `Locator` objects (both sync and async):

- **Page methods**: `goto`, `click`, `fill`, `press`, `type`, `select_option`, `check`, `uncheck`, `wait_for_selector`, `wait_for_load_state`, `wait_for_url`, `wait_for_timeout`, `screenshot`, `pdf`
- **Locator methods**: `click`, `fill`, `press`, `type`, `select_option`, `check`, `uncheck`, `wait_for`, `screenshot`

**Selector Extraction:**

- For `Locator` methods (e.g., `page.locator("button").click()`), the selector is extracted from the Locator object's internal `_selector` attribute
- For `Page` methods (e.g., `page.click("button")`), the first positional argument or `selector` keyword argument is used
- Methods like `wait_for_selector` have the selector as their primary argument
- Non-selector errors (e.g., navigation timeouts, screenshot failures) may not have a `successSelector`

**For Human Agents:**

The error `description` field includes `| successSelector=<value>` so you can immediately see what element needs to appear on the page. Your job is to perform actions in the browser that make that selector become visible/present. Once the RDP Host detects the selector, the session is marked as successful.

Example: If you see `| successSelector=text=Agent Success` in the error description:
- Type "Agent Success" in a search box and submit
- The text appears on the page
- RDP Host detects it and marks the task as complete

**Edge Cases:**

- If the selector cannot be extracted (e.g., method uses complex locator chains), `successSelector` will be `null`
- For assertions with `expect()`, the selector is extracted from the underlying Locator or Page object
- Custom error handlers may provide selectors explicitly when triggering support requests manually

### Browser-Specific Behavior

- **Chromium/Chrome/Edge**: `debugPort` and `targetId` included, precise remote control available via CDP
  - The hook queries Chrome DevTools Protocol's `/json/list` endpoint to resolve the exact CDP target ID for the page
  - This enables the RDP Host to connect to the specific tab even when multiple windows are open
  - Target ID resolution happens automatically based on page URL matching
- **Firefox/WebKit**: `debugPort` and `targetId` omitted, limited remote control

## Detected Errors

The hook specifically listens for:
- ✅ `NeedsAgentInterventionError`

This error can be raised manually in your script when you determine that human/agent assistance is required (e.g., after catching a `TimeoutError` or detecting a CAPTCHA).

**Automatic Context Inheritance:**
When you raise `NeedsAgentInterventionError`, the hook automatically:
1.  Resolves the last active page and browser context
2.  Retrieves the CDP Target ID and Debug Port
3.  **Inherits the selectors** from the last failed Playwright method call (if any)

This means if you catch a `TimeoutError` on `page.click("#btn")` and immediately raise `NeedsAgentInterventionError`, the support request will correctly include `#btn` as the `successSelector`.

**Note:** Both `Page` method errors (e.g., `page.click()`) and `Locator` method errors (e.g., `page.locator().click()`) include full CDP criteria (`debugPort`, `targetId`, `urlContains`, `titleContains`) for accurate tab targeting. The hook automatically resolves the page object from Locator instances to extract browser context and CDP information.

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

1. Check cooldown period (default 0s = no cooldown; can be set via `MINIAGENT_COOLDOWN_SEC`)
2. Verify Flutter has a signed-in user (returns `NO_USER` error otherwise)
3. Check for `BAD_AUTH` errors (token mismatch)
4. Ensure `MINIAGENT_ENABLED=1` (enabled by default)

### CDP not connecting to correct tab

If the RDP Host connects to the wrong browser window/tab:

1. **Check for `targetId` in the support request payload**:
   - When present, the RDP Host can connect directly to the exact tab via CDP
   - Target ID is resolved automatically by querying `http://127.0.0.1:{debugPort}/json/list`
   - Resolution may fail if the page URL changes between error and query
2. **Fallback matching criteria**:
   - If `targetId` is absent, the RDP Host falls back to matching via `urlContains` and `titleContains`
   - Verify these fields are present in logs
   - Both Page and Locator errors should include full CDP criteria
3. **Common issues**:
   - If URL/title are missing, check that `MINIAGENT_REDACT_URLS=1` is not set
   - Multiple tabs with identical URLs may cause ambiguity (targetId resolves this)
   - Very fast navigation after error may invalidate the resolved targetId

### Remote debugging port configuration

For Chromium, the hook automatically injects `--remote-debugging-port` flags by default. This enables Chrome DevTools Protocol (CDP) access for remote control.

**Configuration:**
- `MINIAGENT_DEBUG_PORT=9222` (default) - Base CDP port; hook finds free port starting from this value
- `MINIAGENT_FORCE_DEBUG_PORT=1` (default) - Override any user-provided debug port args

**Dynamic port allocation:**
- The hook uses `_find_free_debug_port()` to automatically find an available port starting from `MINIAGENT_DEBUG_PORT`
- If port 9222 is in use, it tries 9223, 9224, etc. (up to 50 attempts)
- This allows multiple Chromium instances to run concurrently without port conflicts
- The actual chosen port is included in the support request payload's `controlTarget.debugPort`

**Verify CDP is active:**
```bash
# Check if Chromium is listening (use actual port from logs or support request)
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

**Respecting user-provided ports:**
Set `MINIAGENT_FORCE_DEBUG_PORT=0` to preserve any `--remote-debugging-port` args you provide manually in your script. The hook will not inject or override the port in this case.

## Testing the Setup

See `example_playwright_script.py` in this repository for a complete working example. Here's a minimal test:

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
        # Escalate to agent intervention
        # The hook will automatically attach the failing selector from the click() call!
        raise NeedsAgentInterventionError("Button not found, please help!")
    
    print("Test continues after error!")
    input("Press Enter to close browser...")
    browser.close()
```

Run:
```bash
python test_hook.py
```

Expected behavior:
1. Browser opens with remote debugging enabled (check logs for port)
2. After ~5s timeout, error is caught and support request sent
3. Support request includes `debugPort`, `targetId`, `urlContains`, `successSelector`, and `resumeEndpoint`
4. If `MINIAGENT_ON_ERROR=hold` (recommended), script pauses and waits for resume signal
5. If `MINIAGENT_ON_ERROR=report` (default), exception is re-raised after logging

Check Flutter app logs for the incoming support request with full CDP targeting information.

## Uninstalling

To disable the hook:

```bash
export MINIAGENT_ENABLED=0
```

Or remove the `PYTHONPATH` entry.

## License

MIT


