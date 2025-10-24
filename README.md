# Playwright WebSocket Reporter

A robust Python 3.10+ module that detects errors in Playwright tests and immediately notifies a local Flutter desktop app via WebSocket for remote debugging support.

## Overview

When a Playwright test fails, this module:
1. Captures error details, page URL, title, and optional screenshots
2. Extracts Chromium CDP `targetId` for precise tab targeting
3. Sends a support request to your Flutter app over WebSocket
4. Retries automatically on transient failures

The Flutter app receives the support request, creates a Firebase/RTDB entry with control target details, and handles the rest of the remote debugging flow.

## Features

- **Automatic pytest integration**: Plugin auto-loads and reports all test failures
- **Decorator/context manager**: Explicit error wrapping for specific test sections
- **Robust WebSocket protocol**: Hello/auth handshake, ack waiting, exponential backoff
- **Chromium CDP support**: Extracts `targetId` for precise browser tab control
- **CLI tools**: Run tests with reporting or send manual test requests
- **Fully typed**: Pydantic schemas and type hints throughout
- **Comprehensive tests**: Unit and integration tests included

## Installation

### Using a Virtual Environment (Recommended)

On Linux systems with externally-managed Python environments (Ubuntu 24.04+, Debian, etc.):

```bash
# Navigate to the project directory
cd /path/to/detector-rdpbridge

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install the package with dev dependencies
pip install -e ".[dev]"

# Install Playwright browsers
playwright install

# Install system dependencies for Playwright (requires sudo password)
sudo playwright install-deps
```

### Direct Installation

If not using a virtual environment:

```bash
# Clone or copy the package
cd /path/to/detector-rdpbridge

# Install in development mode
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

**Note:** Remember to activate the virtual environment before running any commands:
```bash
source venv/bin/activate
```

## Configuration

All configuration is via environment variables with sensible defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `WS_URL` | `ws://127.0.0.1:8777/ws` | WebSocket endpoint of Flutter app |
| `IPC_TOKEN` | `change-me` | Shared secret for authentication |
| `BROWSER` | `brave` | Browser type (`brave`, `chrome`, `edge`) |
| `DEBUG_PORT` | `9222` | CDP debug port |
| `CONNECT_TIMEOUT_SECONDS` | `5` | Connection timeout |
| `ACK_TIMEOUT_SECONDS` | `5` | Ack waiting timeout |
| `PW_WS_CAPTURE_SCREENSHOT` | `0` | Set to `1` to capture screenshots |
| `PW_WS_TRACE_PATH` | _(none)_ | Optional path to trace file |

Example `.env` file:

```bash
export WS_URL="ws://127.0.0.1:8777/ws"
export IPC_TOKEN="my-secure-token"
export BROWSER="brave"
export DEBUG_PORT="9222"
export PW_WS_CAPTURE_SCREENSHOT="1"
```

## Usage

### 1. Automatic pytest plugin (recommended)

The pytest plugin auto-loads via the `pytest11` entry point. Just run your tests normally:

```bash
pytest tests/test_login.py -v
```

When a test fails, the plugin automatically:
- Extracts the `page` fixture (if available)
- Captures page URL, title, and CDP `targetId`
- Sends a support request to the Flutter app
- Logs the outcome (never crashes the test suite)

### 2. Decorator (auto-detect page)

Wrap individual test functions to add error reporting:

```python
from pw_ws_reporter import report_errors_to_flutter

@report_errors_to_flutter(description_hint="Login flow failed")
async def test_login(page):
    await page.goto("https://example.com/login")
    await page.click("#submit")
    # On any exception, error is reported to Flutter
```

The decorator auto-detects the `page` argument from your test function signature.

### 3. Context manager (explicit page)

For fine-grained control within a test:

```python
from pw_ws_reporter import report_errors_to_flutter

async def test_checkout(page):
    await page.goto("https://example.com")
    
    # Only report errors in this section
    async with report_errors_to_flutter(page, description_hint="Checkout failed"):
        await page.click("#checkout")
        await page.fill("#cc-number", "4242424242424242")
        await page.click("#submit")
```

### 4. CLI: Run tests with reporting

```bash
# Run pytest with the plugin
pw-ws-reporter run pytest tests/ -v

# Run a specific test
pw-ws-reporter run pytest tests/test_login.py::test_submit -q

# Enable verbose logging
pw-ws-reporter --verbose run pytest tests/
```

The `run` command executes your test command and passes through the exit code.

### 5. CLI: Send manual test request

Test connectivity without running actual tests:

```bash
# Minimal test
pw-ws-reporter send --desc "Manual test error"

# With page details
pw-ws-reporter send \
  --desc "Login button not found" \
  --url "https://example.com/login" \
  --title "Login Page" \
  --target-id "ABC123"

# With verbose output
pw-ws-reporter --verbose send --desc "Test"
```

On success, prints:

```
✓ Success!
  Room ID: room-abc123
  Request ID: req-456def
```

## WebSocket Protocol

### Client → Server: Hello/Auth

```json
{
  "type": "hello",
  "token": "change-me",
  "client": "playwright-reporter",
  "version": "1.0"
}
```

### Server → Client: Hello Ack

```json
{
  "type": "hello_ack"
}
```

### Client → Server: Support Request

```json
{
  "type": "support_request",
  "payload": {
    "description": "Playwright failure: Timeout waiting for locator('#submit')",
    "controlTarget": {
      "browser": "brave",
      "debugPort": 9222,
      "urlContains": "https://example.com/login",
      "titleContains": "Dashboard",
      "targetId": "optional-cdp-target-id"
    },
    "meta": {
      "testName": "tests/test_login.py::test_submit",
      "timestamp": "2025-10-24T12:34:56.789Z",
      "screenshotB64": "optional-base64-data",
      "tracePath": "optional-trace.zip"
    }
  }
}
```

### Server → Client: Support Request Ack

```json
{
  "type": "support_request_ack",
  "roomId": "room-abc123",
  "requestId": "req-456def"
}
```

## Flutter App Coordination

The Python reporter **never talks to Firebase** directly. It only sends WebSocket messages to your local Flutter app, which:

1. Runs a WebSocket server at `ws://127.0.0.1:8777/ws`
2. Validates the `IPC_TOKEN` on hello
3. Receives support requests with `controlTarget` details
4. Creates the support request in Firebase/RTDB
5. Seeds the control target data (browser, debugPort, urlContains, titleContains, targetId)
6. Starts the CDP connection and normal remote debugging flow
7. Sends `support_request_ack` back to Python with `roomId` and `requestId`

### Flutter WebSocket Server Example

Your Flutter app should expose something like:

```dart
final server = await HttpServer.bind('127.0.0.1', 8777);
await for (HttpRequest request in server) {
  if (WebSocketTransformer.isUpgradeRequest(request)) {
    WebSocket socket = await WebSocketTransformer.upgrade(request);
    
    socket.listen((message) {
      final data = jsonDecode(message);
      
      if (data['type'] == 'hello') {
        if (data['token'] == expectedToken) {
          socket.add(jsonEncode({'type': 'hello_ack'}));
        }
      } else if (data['type'] == 'support_request') {
        // Create support request in Firebase
        final roomId = await createSupportRequest(data['payload']);
        
        // Send ack
        socket.add(jsonEncode({
          'type': 'support_request_ack',
          'roomId': roomId,
          'requestId': generateRequestId(),
        }));
      }
    });
  }
}
```

## CDP Target ID (Chromium only)

The reporter attempts to extract the CDP `targetId` for Chromium-based browsers (Chrome, Brave, Edge). This allows your Flutter app to attach to the exact browser tab that failed.

**How it works:**
1. Create a CDP session: `page.context.new_cdp_session(page)`
2. Call `Target.getTargetInfo` via CDP
3. Extract `targetInfo.targetId`

**Limitations:**
- Only works for Chromium (not Firefox or WebKit)
- Gracefully skips if CDP fails; still sends the support request without `targetId`

## Error Handling

The reporter is designed to **never crash your test suite**:

- Network errors are logged but don't fail tests
- Missing `page` fixture is handled gracefully (sends description only)
- CDP errors (non-Chromium, permissions) are logged and skipped
- Screenshot failures don't block the support request
- All exceptions during reporting are caught and logged

Tests continue to fail normally; the reporter just adds a side-effect notification.

## Development

### Run tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_ws_client.py -v

# Run with coverage
pytest tests/ --cov=pw_ws_reporter --cov-report=html
```

### Test structure

- `tests/test_schema.py`: Pydantic model validation
- `tests/test_ws_client.py`: WebSocket handshake and basic operations
- `tests/test_retry.py`: Retry and backoff logic with flaky servers
- `tests/test_pytest_plugin.py`: Plugin behavior and error capture
- `tests/test_integration.py`: End-to-end protocol compliance

### Logging

Enable debug logging to see WebSocket traffic:

```bash
pw-ws-reporter --verbose send --desc "Test"
```

Or in code:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Architecture

```
┌─────────────────┐
│  Playwright     │
│  Test Suite     │
└────────┬────────┘
         │ (fail)
         ▼
┌─────────────────┐
│  pytest plugin  │
│  or decorator   │
└────────┬────────┘
         │ report_error()
         ▼
┌─────────────────┐
│  WsClient       │
│  - connect      │
│  - hello/auth   │
│  - send req     │
│  - wait ack     │
│  - retry        │
└────────┬────────┘
         │ WebSocket
         ▼
┌─────────────────┐
│  Flutter App    │
│  - WS server    │
│  - create req   │
│  - seed RTDB    │
│  - start CDP    │
└─────────────────┘
```

## Known Limitations

1. **CDP `targetId` only on Chromium**: Firefox and WebKit don't support CDP
2. **Async-only context manager**: The context manager requires `async with`; sync tests should use the decorator
3. **Single event loop**: The pytest plugin uses a background thread to avoid event loop conflicts
4. **Screenshot timing**: Screenshots are captured after the error, so the page might have changed
5. **No Firebase access**: The Python code never touches Firebase; relies on Flutter app

## Troubleshooting

### "Failed to connect to ws://127.0.0.1:8777/ws"

- Ensure your Flutter app is running
- Check that the WebSocket server is listening on port 8777
- Verify firewall settings

### "Timeout waiting for hello_ack"

- Check `IPC_TOKEN` matches between Python and Flutter
- Increase `ACK_TIMEOUT_SECONDS` if network is slow
- Enable verbose logging to see raw WebSocket messages

### "CDP targetId not available"

- This is expected for non-Chromium browsers
- Ensure you're using Chrome, Brave, or Edge for CDP support
- Check that the browser was launched with debugging enabled

### Tests pass but no support requests sent

- Check that the pytest plugin loaded: `pytest --trace-config`
- Verify that the test actually has a `page` fixture
- Enable verbose logging: `pw-ws-reporter --verbose run pytest ...`

### Screenshots not captured

- Set `PW_WS_CAPTURE_SCREENSHOT=1`
- Ensure the page is still available when the error occurs
- Screenshots are best-effort; failure won't block the support request

## License

MIT

## Contributing

Contributions welcome! Please ensure:
- All tests pass: `pytest tests/ -v`
- Code is typed and documented
- New features include tests
- WebSocket protocol changes are coordinated with Flutter app

## Support

For issues with:
- **Python reporter**: Open an issue in this repository
- **Flutter app integration**: Check your Flutter app's WebSocket server implementation
- **Firebase/RTDB**: That's handled by the Flutter app, not this module

