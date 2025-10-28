# Smoke Tests

These tests verify that the MiniAgent hook correctly intercepts Playwright errors and sends support requests to the Flutter app.

## Prerequisites

1. Set up environment variables (see main README.md)
2. Install dependencies: `pip install -r requirements.txt`
3. Install Playwright browsers: `playwright install`
4. **Start your Flutter app** with the local WebSocket server running on port 8777

## Running Tests

### Individual Tests

```bash
# Chromium timeout
python tests/test_chromium_timeout.py

# Firefox timeout
python tests/test_firefox_timeout.py

# WebKit timeout
python tests/test_webkit_timeout.py

# Multiple errors (cooldown test)
python tests/test_multiple_errors.py

# Assertion error
python tests/test_assertion_error.py
```

### All Tests

```bash
# Linux/Mac
for test in tests/test_*.py; do python "$test"; done

# Windows (PowerShell)
Get-ChildItem tests\test_*.py | ForEach-Object { python $_.FullName }
```

## Expected Behavior

Each test should:
1. ✅ Launch the browser
2. ✅ Trigger a Playwright error (timeout, assertion, etc.)
3. ✅ Catch the error without exiting
4. ✅ Send a support request to Flutter WebSocket server
5. ✅ Keep the browser running
6. ✅ Complete successfully

## Verifying Support Requests

Check your Flutter app logs for messages like:

```
[INFO] WebSocket connected...
[INFO] Handshake complete
[INFO] Support request acknowledged: <requestId> (room: <roomId>)
```

You should also see the support request appear in your Flutter UI.

## Test Details

### test_chromium_timeout.py
- Tests Chromium with auto-injected remote debugging port
- Verifies `controlTarget.debugPort` is included in the request
- Browser: Chromium

### test_firefox_timeout.py
- Tests Firefox (no CDP support)
- Verifies support request is sent without `debugPort`
- Browser: Firefox

### test_webkit_timeout.py
- Tests WebKit (no CDP support)
- Verifies support request is sent without `debugPort`
- Browser: WebKit

### test_multiple_errors.py
- Tests cooldown/deduplication
- Triggers 3 errors in quick succession
- Only the first should send a support request (others deduplicated)

### test_assertion_error.py
- Tests Playwright `expect()` assertion failures
- Verifies AssertionError is caught and reported

## Troubleshooting

### "No support request received in Flutter"

1. Check Flutter logs for connection errors
2. Verify `MINIAGENT_TOKEN` matches Flutter configuration
3. Ensure Flutter user is signed in (returns `NO_USER` otherwise)
4. Check network: `curl http://127.0.0.1:8777` should respond

### "Hook not activating"

1. Verify `PYTHONPATH` includes the detector-rdpbridge directory:
   ```bash
   python -c "import sys; print('\n'.join(sys.path))"
   ```
2. Check that `sitecustomize.py` is being loaded:
   ```bash
   python -c "import sitecustomize; print('Hook loaded')"
   ```
3. Ensure `MINIAGENT_ENABLED=1` and `MINIAGENT_TOKEN` is set

### "Browser doesn't open"

Playwright browsers not installed. Run:
```bash
playwright install
```

### "Module not found: websocket"

Install dependencies:
```bash
pip install -r requirements.txt
```


