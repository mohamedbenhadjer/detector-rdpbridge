# CDP Port 9222 Implementation Summary

## Overview

Successfully implemented forced Chrome DevTools Protocol (CDP) port configuration to ensure Chromium always launches with a consistent debug port (default: 9222).

## Changes Made

### 1. Code Changes (`sitecustomize.py`)

#### Added Configuration Variables (Lines 29-31)
```python
# Remote debugging port configuration
_DEBUG_PORT = int(os.environ.get("MINIAGENT_DEBUG_PORT", "9222"))
_FORCE_DEBUG_PORT = os.environ.get("MINIAGENT_FORCE_DEBUG_PORT", "1") == "1"
```

#### Updated `_inject_debug_args` Function (Lines 123-144)
- Removes existing `--remote-debugging-port` and `--remote-debugging-address` args when `MINIAGENT_FORCE_DEBUG_PORT=1`
- Injects `--remote-debugging-port=<MINIAGENT_DEBUG_PORT>` (default 9222)
- Logs the injected port for debugging

#### Updated `_patched_sync_launch` (Lines 167-193)
- Sets `debug_port = _DEBUG_PORT` for Chromium-based browsers
- Stores the known port in `_browser_info`
- Logs "Chromium launched with debug port {port}"

#### Updated `_patched_sync_launch_persistent` (Lines 200-230)
- Sets `debug_port = _DEBUG_PORT` for persistent contexts
- Performs sanity check by reading `DevToolsActivePort` file
- Warns if detected port doesn't match configured port
- Logs "Chromium persistent context launched with debug port {port}"

### 2. Documentation Updates

#### README.md
- Added `MINIAGENT_DEBUG_PORT` and `MINIAGENT_FORCE_DEBUG_PORT` to configuration table
- Updated "Remote debugging port configuration" section with:
  - Explanation of default port 9222
  - Configuration options
  - `curl` verification command
  - Guidance for multiple concurrent browsers

#### IMPLEMENTATION_COMPLETE.md
- Updated "Remote Debugging" section to reflect forced port 9222
- Added note about configurability
- Updated "Known Limitations" to mention concurrent browser handling

#### TROUBLESHOOTING.md
- Completely rewrote "Chromium debug port not detected" section
- Added new "Port 9222 already in use" troubleshooting section
- Added "Verify CDP Connection" section with `curl` examples
- Updated diagnostics to use `curl http://127.0.0.1:9222/json/version`

### 3. Setup Scripts

#### setup_env.sh (Linux/Mac)
- Added `export MINIAGENT_DEBUG_PORT=9222`
- Added `export MINIAGENT_FORCE_DEBUG_PORT=1`

#### setup_env.bat (Windows)
- Added `set MINIAGENT_DEBUG_PORT=9222`
- Added `set MINIAGENT_FORCE_DEBUG_PORT=1`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIAGENT_DEBUG_PORT` | `9222` | The port number for Chrome DevTools Protocol |
| `MINIAGENT_FORCE_DEBUG_PORT` | `1` | Force override of user-provided debug port args (0=disabled) |

## Verification Steps

### 1. Basic Verification
```bash
# Source the environment
source setup_env.sh

# Set your token
export MINIAGENT_TOKEN="your-token"

# Run a test script
python example_playwright_script.py
```

### 2. Verify CDP is Active
While the browser is running, in another terminal:
```bash
# Check if Chromium is listening on port 9222
curl http://127.0.0.1:9222/json/version

# List all open pages/tabs
curl http://127.0.0.1:9222/json/list

# Or open in browser
# Navigate to: http://127.0.0.1:9222
```

### 3. Expected Behavior

**Console Output:**
```
[miniagent.hook] INFO: Chromium launched with debug port 9222
```

**WebSocket Payload (sent to Flutter app):**
```json
{
  "type": "support_request",
  "payload": {
    "description": "TimeoutError: ...",
    "controlTarget": {
      "browser": "chromium",
      "debugPort": 9222,
      "urlContains": "https://example.com",
      "titleContains": "Example Domain"
    },
    "meta": {
      "runId": "...",
      "pid": 12345,
      "reason": "TimeoutError",
      "ts": "2025-10-28T..."
    }
  }
}
```

**CDP Response:**
```json
{
   "Browser": "Chrome/131.0.6778.85",
   "Protocol-Version": "1.3",
   "User-Agent": "Mozilla/5.0 ...",
   "V8-Version": "13.1.201.11",
   "WebKit-Version": "537.36",
   "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/..."
}
```

## Use Cases

### Single Browser (Default)
```bash
# Uses port 9222 automatically
export MINIAGENT_DEBUG_PORT=9222
export MINIAGENT_FORCE_DEBUG_PORT=1
python my_test.py
```

### Multiple Concurrent Browsers
```bash
# Option 1: Use different ports
export MINIAGENT_DEBUG_PORT=9223
python test1.py &
export MINIAGENT_DEBUG_PORT=9224
python test2.py &

# Option 2: Disable force mode and set in code
export MINIAGENT_FORCE_DEBUG_PORT=0
# Then in your script:
# browser = p.chromium.launch(args=["--remote-debugging-port=9300"])
```

### Custom Port
```bash
export MINIAGENT_DEBUG_PORT=8888
python my_test.py
# CDP available at http://127.0.0.1:8888
```

### Respect User Args
```bash
# Disable forcing to allow user-provided args
export MINIAGENT_FORCE_DEBUG_PORT=0
python my_test.py
# Script must provide --remote-debugging-port in launch args
```

## Benefits

1. **Consistent Port**: Always know where to connect for CDP
2. **Reliable Remote Control**: Flutter app can reliably connect to Chromium
3. **Simplified Configuration**: No need to parse dynamic ports from files
4. **Better Error Messages**: Clear logging when port conflicts occur
5. **Flexible**: Can be disabled or customized via environment variables

## Backward Compatibility

- **Default behavior changed**: Previously used ephemeral port (0), now uses 9222
- **Old behavior available**: Set `MINIAGENT_DEBUG_PORT=0` and `MINIAGENT_FORCE_DEBUG_PORT=0` to get old behavior
- **No code changes needed**: Existing Playwright scripts work without modification

## Testing Checklist

- [x] Code implementation complete
- [x] Documentation updated
- [x] Setup scripts updated
- [ ] Manual verification (run example script)
- [ ] Verify CDP accessible via curl
- [ ] Verify debugPort in WebSocket payload
- [ ] Test with multiple concurrent browsers
- [ ] Test with custom port configuration

## Next Steps

1. Run manual verification:
   ```bash
   cd /home/mohamed/detector-rdpbridge
   source setup_env.sh
   export MINIAGENT_TOKEN="your-token"
   python example_playwright_script.py
   ```

2. In another terminal while script is running:
   ```bash
   curl http://127.0.0.1:9222/json/version
   ```

3. Check logs for:
   - `Chromium launched with debug port 9222`
   - WebSocket message containing `"debugPort": 9222`

## Troubleshooting

**If port 9222 already in use:**
```bash
# Find the process
lsof -i :9222

# Kill it
pkill -f chromium

# Or use a different port
export MINIAGENT_DEBUG_PORT=9223
```

**If CDP not accessible:**
```bash
# Check if browser is running
ps aux | grep chromium

# Check if port is listening
lsof -i :9222
netstat -an | grep 9222

# Check logs
python -c "import logging; logging.basicConfig(level=logging.DEBUG); import sitecustomize"
```

## Files Modified

1. `sitecustomize.py` - Core implementation
2. `README.md` - User documentation
3. `IMPLEMENTATION_COMPLETE.md` - Feature documentation
4. `TROUBLESHOOTING.md` - Debug guide
5. `setup_env.sh` - Linux/Mac setup
6. `setup_env.bat` - Windows setup

---

**Implementation Date:** October 28, 2025  
**Version:** 2.0  
**Status:** ✅ Complete (pending manual verification)





