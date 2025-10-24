# Testing Guide for pw-ws-reporter

## Quick Test with Failing Playwright Tests

I've created `test_demo_failure.py` with 4 intentionally failing Playwright tests to help you verify the reporter works.

### Prerequisites

1. **Install Playwright browsers** (if not already done):
   ```bash
   playwright install chromium
   ```

2. **Start your Flutter WebSocket server** on `ws://127.0.0.1:8777/ws`

3. **Set environment variables** (optional, uses defaults):
   ```bash
   export WS_URL=ws://127.0.0.1:8777/ws
   export IPC_TOKEN=change-me
   export BROWSER=brave
   ```

### Test Scenarios

Run these tests to verify the reporter:

#### Test 1: Single failing test (quickest)
```bash
pytest test_demo_failure.py::test_missing_element_failure -v
```
**Expected:**
- Test fails with timeout error
- Support request sent to Flutter with:
  - URL: https://example.com
  - Title: "Example Domain"
  - Description: timeout error details
  - CDP targetId (if Chromium)

#### Test 2: Run all failing tests
```bash
pytest test_demo_failure.py -v
```
**Expected:**
- All 4 tests fail
- 4 separate support requests sent to Flutter
- Each with different error details

#### Test 3: With verbose logging
```bash
pw-ws-reporter --verbose run -- pytest test_demo_failure.py::test_assertion_failure -v
```
**Expected:**
- You'll see WebSocket connection logs
- "Support request sent successfully: roomId=..., requestId=..."
- Or connection errors if Flutter isn't running

#### Test 4: With screenshot capture
```bash
PW_WS_CAPTURE_SCREENSHOT=1 pytest test_demo_failure.py::test_missing_element_failure -v
```
**Expected:**
- Support request includes base64-encoded screenshot
- Flutter receives screenshot data in `meta.screenshotB64`

### Without Flutter Running (Test Locally)

If Flutter isn't running, you'll see connection errors but tests still fail normally:

```bash
pytest test_demo_failure.py::test_missing_element_failure -v
```

**Expected:**
- Test fails as expected
- Reporter logs: "Failed to connect to ws://127.0.0.1:8777/ws"
- Test suite completes normally (reporter never crashes tests)

### What to Check in Your Flutter App

When a test fails, your Flutter WebSocket server should receive:

1. **Hello message** (first connection):
   ```json
   {
     "type": "hello",
     "token": "change-me",
     "client": "playwright-reporter",
     "version": "1.0"
   }
   ```

2. **Support request**:
   ```json
   {
     "type": "support_request",
     "payload": {
       "description": "Playwright failure: TimeoutError...",
       "controlTarget": {
         "browser": "brave",
         "debugPort": 9222,
         "urlContains": "https://example.com",
         "titleContains": "Example Domain",
         "targetId": "ABC123..."
       },
       "meta": {
         "testName": "test_demo_failure.py::test_missing_element_failure",
         "timestamp": "2025-10-24T...",
         "screenshotB64": null,
         "tracePath": null
       }
     }
   }
   ```

3. **Your Flutter app should reply**:
   - `{"type": "hello_ack"}` for hello
   - `{"type": "support_request_ack", "roomId": "...", "requestId": "..."}` for support request

### Troubleshooting

**"Failed to connect"**
- Ensure Flutter WebSocket server is running
- Check the port: `netstat -an | grep 8777`
- Verify WS_URL matches your Flutter server

**"Timeout waiting for hello_ack"**
- Check IPC_TOKEN matches between Python and Flutter
- Increase timeout: `export ACK_TIMEOUT_SECONDS=10`

**"No support request sent"**
- Enable verbose: `pw-ws-reporter --verbose run -- pytest ...`
- Check if page fixture is available in the test
- Verify the package is installed: `pip show pw-ws-reporter`

**Tests don't fail**
- The demo tests are designed to fail on purpose
- If they pass, something's wrong with the test file

### Manual Test (No Playwright Required)

Test connectivity without running Playwright:

```bash
pw-ws-reporter send \
  --desc "Manual test from terminal" \
  --url "https://example.com" \
  --title "Example Domain" \
  --test-name "manual_test"
```

**Expected output if Flutter is running:**
```
✓ Success!
  Room ID: room-abc123
  Request ID: req-456def
```

**Expected output if Flutter is NOT running:**
```
✗ Failed to send support request
```

### Next Steps

Once you've verified the reporter works:

1. Delete `test_demo_failure.py` (it's just for testing)
2. Use the reporter with your real Playwright tests
3. Configure environment variables for your setup
4. Let tests run normally - failures are auto-reported

See README.md for production usage patterns.

