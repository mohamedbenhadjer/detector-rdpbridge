# MiniAgent Architecture

Technical overview of how the Playwright auto-hook support request system works.

## Overview

The system uses Python's `sitecustomize` auto-loading mechanism to transparently intercept Playwright errors without modifying user code. When errors occur, it sends structured support requests to a local Flutter WebSocket server.

## Components

### 1. sitecustomize.py (Entry Point)

**Purpose**: Auto-loaded by Python interpreter when in PYTHONPATH

**Responsibilities**:
- Detects Playwright installation
- Monkey-patches Playwright APIs
- Intercepts browser launch to inject debug flags
- Catches exceptions and triggers support requests

**Key Functions**:
- `_intercept_playwright()`: Main entry point, applies all patches
- `_inject_debug_args()`: Adds `--remote-debugging-port=0` for Chromium
- `_read_devtools_port()`: Reads the actual port from DevToolsActivePort file
- `_wrap_method()`: Generic wrapper for sync/async methods
- `_get_page_info()`: Extracts URL, title, page ID from Page objects

**Patched Classes**:
- `BrowserType.launch` (sync/async)
- `BrowserType.launch_persistent_context` (sync/async)
- `Page` methods: goto, click, fill, wait_for_*, etc.
- `Locator` methods: click, fill, check, etc.

**Exception Handling**:
- Catches: `TimeoutError`, `Error`, `AssertionError`
- Re-raises all exceptions (report-only mode)
- Extracts context (page URL, title, browser type, debug port)

### 2. miniagent_ws.py (WebSocket Client)

**Purpose**: Manages WebSocket communication with Flutter

**Classes**:

#### MiniAgentWSClient
- Connects to `ws://127.0.0.1:8777/ws`
- Implements handshake protocol (hello → hello_ack)
- Auto-reconnect with exponential backoff (0.5s → 8s)
- Buffers messages when offline
- Thread-safe message queue

**Connection Flow**:
```
Connect → Send hello → Wait for hello_ack → Authenticated → Send messages
```

**Backoff Strategy**:
- Initial delay: 0.5s
- Max delay: 8s
- Doubles on each failure
- Resets to 0.5s on successful connection

#### SupportRequestManager
- De-duplicates requests by (runId, page_id)
- Cooldown window (default 20s)
- Builds support_request payloads
- Manages global state (runId, PID)

**Deduplication**:
- Key: (runId, page_id)
- Window: MINIAGENT_COOLDOWN_SEC
- Cleanup: entries older than 2x cooldown removed periodically

**Payload Structure**:
```json
{
  "type": "support_request",
  "payload": {
    "description": "TimeoutError: click: ...",
    "controlTarget": {
      "browser": "chromium|firefox|webkit",
      "debugPort": 9222,  // Chromium only
      "urlContains": "...",
      "titleContains": "..."
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

### 3. Flutter WebSocket Server (External)

**Endpoint**: `ws://127.0.0.1:8777/ws`

**Protocol**:
1. Client connects
2. Client sends `hello` with token within 5s
3. Server validates token, sends `hello_ack`
4. Client can send `support_request` messages
5. Server responds with `support_request_ack` containing requestId/roomId

**Error Responses**:
- `BAD_AUTH`: Invalid token
- `INVALID_PAYLOAD`: Missing or malformed payload
- `NO_USER`: No signed-in user in Flutter app

## Flow Diagrams

### Initialization Flow

```
Python starts
    ↓
sitecustomize.py auto-imported (via PYTHONPATH)
    ↓
Import miniagent_ws
    ↓
Read env vars (MINIAGENT_*)
    ↓
Create MiniAgentWSClient (background thread)
    ↓
Connect to ws://127.0.0.1:8777/ws
    ↓
Send hello handshake
    ↓
Wait for hello_ack
    ↓
Monkey-patch Playwright APIs
    ↓
User's Playwright script starts
```

### Error Detection Flow

```
User calls page.click(...)
    ↓
Patched method wrapper executes
    ↓
Try original page.click()
    ↓
Exception raised (TimeoutError)
    ↓
Wrapper catches exception
    ↓
Extract context (URL, title, page_id)
    ↓
Get browser info (type, debug_port)
    ↓
Call SupportRequestManager.trigger_support_request()
    ↓
Check deduplication (runId, page_id)
    ↓
Build payload (description, controlTarget, meta)
    ↓
Send to MiniAgentWSClient
    ↓
WebSocket sends support_request to Flutter
    ↓
Wait for support_request_ack
    ↓
Re-raise exception (script continues/handles)
```

### Browser Launch Flow (Chromium)

```
User calls p.chromium.launch()
    ↓
Patched launch() executes
    ↓
Inject --remote-debugging-port=0 to args
    ↓
Call original launch()
    ↓
Browser starts, writes DevToolsActivePort file
    ↓
Sleep 500ms (give Chrome time to write file)
    ↓
Read DevToolsActivePort file
    ↓
Parse port number (e.g., 9222)
    ↓
Store browser info: {browser: "chromium", debug_port: 9222}
    ↓
Return browser object to user
    ↓
On future errors, include debug_port in controlTarget
```

### Browser Launch Flow (Firefox/WebKit)

```
User calls p.firefox.launch()
    ↓
Patched launch() executes
    ↓
No debug port injection (not supported)
    ↓
Call original launch()
    ↓
Store browser info: {browser: "firefox", debug_port: None}
    ↓
Return browser object to user
    ↓
On future errors, omit debug_port from controlTarget
```

## Threading Model

### Main Thread
- Runs user's Playwright script
- Executes patched methods
- Raises/catches exceptions

### WebSocket Thread (Daemon)
- Background thread started by MiniAgentWSClient
- Runs WebSocket event loop (run_forever)
- Handles send/receive
- Auto-reconnects on disconnect

**Thread Safety**:
- `threading.Lock` protects message queue and authentication state
- Deduplication cache uses lock for concurrent access

## Security

### Loopback Only
- WebSocket connects to 127.0.0.1 (local only)
- No external network traffic
- No firewall changes needed

### Authentication
- Shared token (MINIAGENT_TOKEN)
- Must match Flutter server configuration
- Rejected immediately on mismatch (BAD_AUTH)

### Privacy
- URL/title redaction via MINIAGENT_REDACT_URLS=1
- No screenshot/trace capture by default
- No PII beyond what's in error messages

### Data Minimization
- Description truncated to 500 chars
- URL/title truncated to 100 chars
- Only whitelisted controlTarget fields sent

## Performance

### Overhead
- Import time: ~50-200ms (one-time on script start)
- Per-error overhead: ~5-10ms (exception capture + payload build)
- No overhead on successful operations

### Resource Usage
- Memory: ~5-10 MB (WebSocket client + state)
- CPU: negligible (background thread idle until send)
- Network: minimal (small JSON messages on errors only)

### Scalability
- Handles hundreds of errors with deduplication
- Cooldown prevents spam
- Backoff prevents CPU spin on connection failures

## Compatibility

### Python Versions
- Requires: Python 3.7+ (for async/await, type hints)
- Tested: 3.8, 3.9, 3.10, 3.11

### Playwright Versions
- Minimum: 1.40.0
- Tested: 1.40+, 1.45+
- Uses public API only (stable across versions)

### Operating Systems
- Linux: Full support
- Windows: Full support
- macOS: Full support (not yet tested)

### Browsers
| Browser | Support | Debug Port | Remote Control |
|---------|---------|------------|----------------|
| Chromium | ✅ Full | ✅ Auto | ✅ CDP |
| Chrome | ✅ Full | ✅ Auto | ✅ CDP |
| Edge | ✅ Full | ✅ Auto | ✅ CDP |
| Firefox | ✅ Partial | ❌ N/A | ❌ Limited |
| WebKit | ✅ Partial | ❌ N/A | ❌ Limited |

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PYTHONPATH` | path | - | Must include project dir |
| `MINIAGENT_ENABLED` | bool | 1 | Enable/disable hook |
| `MINIAGENT_WS_URL` | url | ws://127.0.0.1:8777/ws | WebSocket server |
| `MINIAGENT_TOKEN` | string | - | Auth token (required) |
| `MINIAGENT_CLIENT` | string | python-cdp-monitor | Client name |
| `MINIAGENT_COOLDOWN_SEC` | int | 20 | Dedup cooldown |
| `MINIAGENT_REDACT_URLS` | bool | 0 | Redact URLs/titles |

### Runtime State

**Per-Process**:
- runId: 8-char UUID segment
- PID: process ID
- Recent triggers cache
- WebSocket connection state

**Per-Browser**:
- Browser type (chromium/firefox/webkit)
- Debug port (Chromium only)
- Stored by object ID

**Per-Page**:
- Page ID: Python object ID
- URL, title (extracted on error)

## Error Handling

### Hook Initialization Failures
- Missing dependencies: Log warning, disable hook
- Import errors: Silent fail (don't break user script)
- Token missing: Log warning, disable support requests

### WebSocket Failures
- Connection refused: Auto-retry with backoff
- Auth failure (BAD_AUTH): Stop retrying, log error
- NO_USER error: Queue message, retry periodically
- Disconnect: Auto-reconnect

### Browser Launch Failures
- DevToolsActivePort not found: Continue without port
- Port file read error: Continue without port
- Launch exception: Re-raise (don't hide user errors)

## Debugging

### Enable Debug Logs

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or:
```bash
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
python -c "import logging; logging.basicConfig(level=logging.DEBUG); import sitecustomize"
```

### Verification Script

```bash
python verify_setup.py
```

### Test Hook Loading

```bash
python -c "import sitecustomize; print('Hook loaded')"
```

### Check WebSocket Connection

```bash
python -c "from miniagent_ws import get_support_manager; m = get_support_manager(); import time; time.sleep(2)"
```

Look for:
```
[INFO] Connecting to ws://127.0.0.1:8777/ws...
[INFO] WebSocket connected, sending hello...
[INFO] Handshake complete
[INFO] MiniAgent initialized (runId: a1b2c3d4)
```

## Extending

### Custom Error Handlers

Modify `sitecustomize.py` to add custom logic in the wrapper:

```python
def _sync_wrapper(self, *args, **kwargs):
    try:
        return orig_method(self, *args, **kwargs)
    except Exception as e:
        # Your custom logic here
        manager.trigger_support_request(...)
        raise
```

### Additional Patching

Add more classes/methods to the patch list:

```python
# Patch additional methods
for method in ["my_custom_method"]:
    if hasattr(SyncPage, method):
        _wrap_method(SyncPage, method, is_async=False)
```

### Custom Payload Fields

Modify `SupportRequestManager.trigger_support_request()` to include additional metadata:

```python
meta = {
    "runId": self.run_id,
    "pid": self.pid,
    "reason": reason,
    "ts": datetime.now(timezone.utc).isoformat(),
    "custom_field": "value"  # Add here
}
```

## Future Enhancements

### Potential Additions
- Screenshot capture on error (opt-in)
- HAR/network log collection
- Process heartbeat for "lost control" detection
- Async API support (currently sync-focused)
- pytest plugin mode
- Configuration file support (.miniagent.toml)
- Multiple WebSocket servers (failover)

### Not Planned
- Modifying user Playwright code
- Wrapping script execution
- Process lifecycle management
- Browser automation (that's Flutter's job)


