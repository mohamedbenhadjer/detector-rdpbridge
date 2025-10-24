# Setup Complete! 🎉

Your Playwright WebSocket Reporter package has been successfully installed in a virtual environment.

## What Was Done

✅ Created virtual environment at `venv/`  
✅ Installed package in editable mode with dev dependencies  
✅ Installed Playwright browsers (Firefox, WebKit)  
✅ All 31 tests passed successfully  
✅ CLI command `pw-ws-reporter` is available  
✅ Created `activate.sh` helper script  
✅ Updated README with virtual environment instructions  

## Next Steps

### 1. Install Playwright System Dependencies (Required)

The Playwright browsers need system libraries. Run this command and enter your password:

```bash
source venv/bin/activate
sudo playwright install-deps
```

This installs missing dependencies like `libavif16` and others required by the browsers.

### 2. Activate the Virtual Environment

Every time you open a new terminal, activate the virtual environment:

```bash
# Option 1: Use the helper script
source activate.sh

# Option 2: Manual activation
source venv/bin/activate
```

### 3. Test the Installation

Try the CLI:

```bash
# Activate first
source venv/bin/activate

# Test the help command
pw-ws-reporter --help

# Send a test message (requires Flutter app running)
pw-ws-reporter send --desc "Test message"

# Run the test suite
pytest tests/ -v
```

### 4. Run Your Own Tests

```bash
# Activate the environment
source venv/bin/activate

# Run your Playwright tests
pytest examples/ -v

# Or use the CLI wrapper
pw-ws-reporter run pytest examples/ -v
```

## Environment Variables

Configure the WebSocket connection by setting environment variables:

```bash
export WS_URL="ws://127.0.0.1:8777/ws"
export IPC_TOKEN="your-secure-token"
export BROWSER="brave"
export DEBUG_PORT="9222"
export PW_WS_CAPTURE_SCREENSHOT="1"
```

Or create a `.env` file and source it:

```bash
source .env
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `source activate.sh` | Activate virtual environment |
| `deactivate` | Deactivate virtual environment |
| `pw-ws-reporter --help` | Show CLI help |
| `pytest tests/ -v` | Run all tests |
| `pytest examples/ -v` | Run example tests |

## Troubleshooting

### "Command not found: pw-ws-reporter"
→ Activate the virtual environment first: `source venv/bin/activate`

### "Failed to connect to ws://127.0.0.1:8777/ws"
→ Ensure your Flutter app WebSocket server is running

### Missing system libraries error
→ Run: `sudo playwright install-deps`

## More Information

- Full documentation: See `README.md`
- Quick start guide: See `QUICKSTART.md`
- Example tests: See `examples/` directory
- Unit tests: See `tests/` directory

---

**Pro Tip:** Add `source venv/bin/activate` to your shell profile or use a tool like `direnv` to auto-activate when entering this directory.

