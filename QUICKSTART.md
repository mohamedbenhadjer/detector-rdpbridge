# Quick Start Guide

## Installation

```bash
# Install the package
pip install -e .

# Or with dev dependencies for testing
pip install -e ".[dev]"
```

## Verify Installation

```bash
# Check CLI is available
pw-ws-reporter --help

# Run the test suite
pytest tests/ -v
```

## Basic Usage

### 1. Automatic Plugin (Easiest)

Just run pytest normally - the plugin auto-loads:

```bash
pytest tests/
```

When a test with a `page` fixture fails, it automatically sends a support request to the Flutter app.

### 2. Using the Decorator

```python
from pw_ws_reporter import report_errors_to_flutter

@report_errors_to_flutter(description_hint="Login failed")
async def test_login(page):
    await page.goto("https://example.com/login")
    await page.fill("#username", "test")
    await page.fill("#password", "pass")
    await page.click("#submit")
    # If this fails, error is reported
```

### 3. Using the Context Manager

```python
from pw_ws_reporter import report_errors_to_flutter

async def test_checkout(page):
    await page.goto("https://example.com")
    
    # Only report errors in this block
    async with report_errors_to_flutter(page, description_hint="Checkout failed"):
        await page.click("#checkout-button")
        await page.fill("#cc-number", "4242424242424242")
        await page.click("#submit")
```

### 4. Using the CLI

```bash
# Run pytest via the CLI
pw-ws-reporter run pytest tests/test_login.py -v

# Send a manual test support request
pw-ws-reporter send --desc "Test error" --url "https://example.com"
```

## Configuration

Set environment variables:

```bash
export WS_URL="ws://127.0.0.1:8777/ws"
export IPC_TOKEN="my-secure-token"
export BROWSER="brave"
export DEBUG_PORT="9222"
export PW_WS_CAPTURE_SCREENSHOT="1"
```

## Flutter App Requirements

Your Flutter app must:

1. Run a WebSocket server at `ws://127.0.0.1:8777/ws` (or your configured URL)
2. Accept `hello` messages and reply with `hello_ack`
3. Accept `support_request` messages and reply with `support_request_ack` containing `roomId` and `requestId`
4. Create the support request in Firebase/RTDB with the control target details

See the README for full protocol details.

## Examples

Check the `examples/` directory for:
- `test_example_auto_plugin.py` - Auto plugin usage
- `test_example_decorator.py` - Decorator patterns
- `test_example_context_manager.py` - Context manager patterns

## Troubleshooting

**Connection errors?**
- Ensure your Flutter app is running
- Check the WebSocket URL and port
- Verify firewall settings

**No support requests sent?**
- Check that tests actually have a `page` fixture
- Enable verbose logging: `pw-ws-reporter --verbose run pytest ...`
- Verify `IPC_TOKEN` matches between Python and Flutter

**CDP targetId not available?**
- This is normal for non-Chromium browsers (Firefox, WebKit)
- Ensure browser is launched with debugging enabled for Chromium

## Next Steps

1. Start your Flutter app with WebSocket server running
2. Run your Playwright tests
3. When a test fails, check your Flutter app for the support request
4. The Flutter app should create the support request in Firebase and start the CDP connection

For more details, see the [README.md](README.md).

