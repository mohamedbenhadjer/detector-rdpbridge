# Troubleshooting Guide

Common issues and solutions for MiniAgent.

## Table of Contents
- [Setup Issues](#setup-issues)
- [Connection Issues](#connection-issues)
- [Hook Not Activating](#hook-not-activating)
- [No Support Requests Sent](#no-support-requests-sent)
- [Browser Issues](#browser-issues)
- [Performance Issues](#performance-issues)
- [Platform-Specific Issues](#platform-specific-issues)

---

## Setup Issues

### "ModuleNotFoundError: No module named 'websocket'"

**Cause**: Missing websocket-client dependency

**Solution**:
```bash
pip install websocket-client
```

Or install all dependencies:
```bash
pip install -r requirements.txt
```

---

### "ModuleNotFoundError: No module named 'playwright'"

**Cause**: Playwright not installed

**Solution**:
```bash
pip install playwright
playwright install
```

---

### "sitecustomize not found"

**Cause**: PYTHONPATH doesn't include the project directory

**Solution**:

Linux/Mac:
```bash
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
```

Windows (PowerShell):
```powershell
$env:PYTHONPATH = "C:\Users\YourUser\detector-rdpbridge;$env:PYTHONPATH"
```

Verify:
```bash
python -c "import sys; print('\n'.join(sys.path))"
```

Should include `/home/mohamed/detector-rdpbridge`.

---

### "verify_setup.py shows failures"

**Cause**: Incomplete setup

**Solution**: Run through each failed check:

1. **PYTHONPATH missing**: Add to environment (see above)
2. **Token not set**: `export MINIAGENT_TOKEN="your-token"`
3. **Dependencies missing**: `pip install -r requirements.txt`
4. **Playwright not installed**: `playwright install`

---

## Connection Issues

### "WebSocket connection failed"

**Symptoms**:
```
[ERROR] WebSocket error: [Errno 111] Connection refused
```

**Causes & Solutions**:

1. **Flutter app not running**
   - Start your Flutter desktop app
   - Ensure the local WebSocket server is active

2. **Wrong port**
   - Check Flutter is listening on port 8777
   - Verify with: `netstat -tlnp | grep 8777` (Linux) or `netstat -an | findstr 8777` (Windows)
   - If different port, set: `export MINIAGENT_WS_URL="ws://127.0.0.1:PORT/ws"`

3. **Firewall blocking**
   - Unlikely for loopback, but check firewall rules
   - Temporarily disable firewall to test

---

### "BAD_AUTH error"

**Symptoms**:
```
[ERROR] Server error: BAD_AUTH - Invalid token
```

**Cause**: Token mismatch between Python and Flutter

**Solution**:
1. Check Flutter app configuration for the shared token
2. Set matching token in Python:
   ```bash
   export MINIAGENT_TOKEN="exact-token-from-flutter"
   ```
3. Restart your Playwright script

---

### "NO_USER error"

**Symptoms**:
```
[WARNING] No signed-in user - will retry later
```

**Cause**: No user is signed into the Flutter app

**Solution**:
1. Sign in to the Flutter app
2. The hook will automatically retry sending the buffered message

---

### "hello_ack not received"

**Symptoms**:
- Connection opens but no handshake completion
- Timeout after 5 seconds

**Causes & Solutions**:

1. **Token mismatch** (see BAD_AUTH above)
2. **Flutter server protocol mismatch**
   - Verify Flutter expects: `{"type": "hello", "token": "...", "client": "...", "version": "1.0"}`
   - Check Flutter logs for handshake errors

---

## Hook Not Activating

### "Hook doesn't intercept errors"

**Symptoms**: Errors occur but no support requests sent

**Diagnosis**:
```bash
# 1. Check if hook loads
python -c "import sitecustomize; print('✓ Hook loaded')"

# 2. Check if Playwright is detected
python -c "from playwright.sync_api import sync_playwright; print('✓ Playwright found')"

# 3. Check if manager initializes
python -c "from miniagent_ws import get_support_manager; m = get_support_manager(); print(f'✓ Manager OK (runId: {m.run_id})')"
```

**Solutions**:

1. **MINIAGENT_ENABLED=0**: Set to 1
   ```bash
   export MINIAGENT_ENABLED=1
   ```

2. **Token missing**: Hook disables if no token
   ```bash
   export MINIAGENT_TOKEN="your-token"
   ```

3. **Import order**: Ensure sitecustomize loads before playwright
   - Should happen automatically via PYTHONPATH
   - Verify: `python -c "import sys; print(sys.path[0:5])"`

4. **Virtual environment**: If using venv, ensure PYTHONPATH is set within it
   ```bash
   # Activate venv first
   source venv/bin/activate
   export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
   ```

---

### "Playwright imports but hook doesn't patch"

**Cause**: Hook initialization failed silently

**Solution**:
Enable debug logging to see errors:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
import sitecustomize
```

Look for:
```
[INFO] Playwright interception activated
```

If missing, check error messages.

---

## No Support Requests Sent

### "Errors caught but no requests in Flutter"

**Diagnosis checklist**:
- [ ] Hook is active (see above)
- [ ] WebSocket connected (check logs for "Handshake complete")
- [ ] Token is correct (no BAD_AUTH errors)
- [ ] User signed in (no NO_USER errors)
- [ ] Cooldown not active (wait 20+ seconds between tests)

**Solutions**:

1. **Cooldown active**
   - Default 20s cooldown prevents duplicates
   - Wait 20+ seconds or reduce: `export MINIAGENT_COOLDOWN_SEC=5`

2. **Buffered messages not flushed**
   - Check WebSocket authentication status
   - Messages buffered until hello_ack received

3. **Flutter not logging**
   - Check Flutter console/logs for incoming WebSocket messages
   - Verify Flutter's support request handler is working

---

### "Only first error sends request, rest ignored"

**Cause**: This is intentional (deduplication)

**Explanation**:
- Within cooldown window (default 20s), duplicate errors on the same page are suppressed
- Prevents spam from retry loops

**To test different errors**:
- Wait 20+ seconds between tests
- Use different pages (different page IDs)
- Reduce cooldown: `export MINIAGENT_COOLDOWN_SEC=5`

---

## Browser Issues

### "Chromium debug port not detected"

**Symptoms**: `controlTarget.debugPort` is null/missing for Chromium

**Diagnosis**:
```bash
# Check if DevToolsActivePort file exists
# (requires knowing user-data-dir, typically in /tmp or C:\Users\...\AppData\Local\Temp)
find /tmp -name "DevToolsActivePort" 2>/dev/null
```

**Causes & Solutions**:

1. **Launch timing**
   - Hook waits 500ms after launch for Chrome to write the file
   - If still missing, increase delay in sitecustomize.py (line ~150)

2. **Headless mode**
   - Remote debugging works in headless too
   - Ensure `--remote-debugging-port=0` is injected (check browser command line)

3. **User data dir not accessible**
   - Permissions issue
   - Temporary directory cleanup
   - Solution: Use `launch_persistent_context` with explicit user_data_dir

---

### "Firefox/WebKit show debugPort"

**Expected behavior**: Firefox and WebKit don't support CDP, so `debugPort` should be null/omitted

**If showing a port**: Bug in browser detection logic

**Workaround**: Check `controlTarget.browser` field to determine if CDP is available

---

### "Browser doesn't stay open after error"

**Cause**: User code explicitly closes browser or raises SystemExit

**Note**: Hook re-raises exceptions but doesn't prevent:
- User's exception handlers that close browser
- `sys.exit()` calls
- Uncaught exceptions at module level

**Solution**: Ensure your script handles exceptions gracefully:
```python
try:
    page.click("button")
except Exception as e:
    print(f"Error: {e}")
    # Don't close browser here
    # Don't call sys.exit()
```

---

## Performance Issues

### "Script startup is slow"

**Cause**: Hook initialization overhead (~50-200ms)

**Solutions**:
1. **Acceptable overhead**: One-time cost per script run
2. **Disable if not needed**: `export MINIAGENT_ENABLED=0`
3. **Virtual environment**: Ensure PYTHONPATH doesn't include too many directories

---

### "Many errors cause delays"

**Cause**: Each error triggers WebSocket send (~5-10ms)

**Solutions**:
1. **Cooldown prevents most overhead**: Duplicates are skipped
2. **Increase cooldown**: `export MINIAGENT_COOLDOWN_SEC=60`
3. **Fix underlying errors**: Reduce error frequency in your scripts

---

## Platform-Specific Issues

### Linux

#### "Permission denied reading DevToolsActivePort"

**Cause**: User data dir permissions

**Solution**:
```bash
# Use explicit user data dir with correct permissions
browser = p.chromium.launch_persistent_context(
    user_data_dir="/home/user/.playwright-chrome",
    # ... other args
)
```

#### "DISPLAY not set (headless needed)"

**Not an issue**: Remote debugging works in headless mode

**If needed**:
```python
browser = p.chromium.launch(headless=True)
```

---

### Windows

#### "PYTHONPATH not persisting"

**Cause**: Environment variable not saved system-wide

**Solution (Permanent)**:
1. Open System Properties → Advanced → Environment Variables
2. Add User variable:
   - Name: `PYTHONPATH`
   - Value: `C:\Users\YourUser\detector-rdpbridge;%PYTHONPATH%`
3. Restart terminal

**Solution (Per-session)**:
Use `setup_env.bat` before running scripts

---

#### "WebSocket error: 10061 Connection refused"

**Cause**: Flutter not listening on 127.0.0.1:8777

**Check**:
```cmd
netstat -an | findstr 8777
```

Should show:
```
TCP    127.0.0.1:8777    0.0.0.0:0    LISTENING
```

---

#### "Path too long errors"

**Cause**: Windows path length limit

**Solution**:
1. Enable long paths: `reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1`
2. Or use shorter directory: `C:\miniagent\`

---

## Debug Mode

### Enable full debug logging

```bash
# Create a test script
cat > debug_test.py << 'EOF'
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)

# Import hook
import sitecustomize

# Import Playwright
from playwright.sync_api import sync_playwright

# Run a simple test
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://example.com")
    try:
        page.click("button:has-text('NonExistent')", timeout=3000)
    except Exception as e:
        print(f"Caught: {e}")
    browser.close()
EOF

python debug_test.py
```

Look for:
```
[miniagent] INFO: MiniAgent initialized (runId: ...)
[miniagent] INFO: Connecting to ws://...
[miniagent] INFO: WebSocket connected, sending hello...
[miniagent] INFO: Handshake complete
[miniagent.hook] INFO: Playwright interception activated
[miniagent] INFO: Triggering support request: TimeoutError
[miniagent] INFO: Sent support request: ...
[miniagent] INFO: Support request acknowledged: ...
```

---

## Still Having Issues?

### Verification Checklist

Run through this complete checklist:

```bash
# 1. Dependencies installed?
pip show playwright websocket-client

# 2. PYTHONPATH set?
python -c "import sys; print('/home/mohamed/detector-rdpbridge' in str(sys.path))"

# 3. Token set?
python -c "import os; print(bool(os.environ.get('MINIAGENT_TOKEN')))"

# 4. Hook loads?
python -c "import sitecustomize; print('OK')"

# 5. Manager initializes?
python -c "from miniagent_ws import get_support_manager; print('OK' if get_support_manager() else 'FAIL')"

# 6. Flutter running?
curl http://127.0.0.1:8777 || echo "Flutter not responding"

# 7. Run verification script
python verify_setup.py
```

### Get Help

If all else fails:
1. Run `python verify_setup.py` and save output
2. Enable debug logging and save output
3. Check Flutter logs for WebSocket errors
4. Review this entire troubleshooting guide
5. Check ARCHITECTURE.md for technical details

### Common Gotchas

- ❌ Forgetting to set `MINIAGENT_TOKEN`
- ❌ PYTHONPATH set in one terminal but running in another
- ❌ Virtual environment: forgetting to activate before setting env vars
- ❌ Expecting immediate retries (cooldown active)
- ❌ Flutter app not running
- ❌ Wrong port (not 8777)
- ❌ Token mismatch between Python and Flutter


