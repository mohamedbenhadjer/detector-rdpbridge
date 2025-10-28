# Quick Start Guide

Get the MiniAgent hook running in 5 minutes.

## 1. Install Dependencies

```bash
cd /home/mohamed/detector-rdpbridge
pip install -r requirements.txt
playwright install chromium  # or firefox, webkit
```

## 2. Set Environment Variables

### Linux (Quick Setup)

```bash
# Source the setup script (adds to current session)
source setup_env.sh

# Set your token (REQUIRED)
export MINIAGENT_TOKEN="your-shared-token-from-flutter"
```

Or add to `~/.bashrc` for persistence:
```bash
echo 'export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"' >> ~/.bashrc
echo 'export MINIAGENT_ENABLED=1' >> ~/.bashrc
echo 'export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"' >> ~/.bashrc
echo 'export MINIAGENT_TOKEN="your-shared-token-from-flutter"' >> ~/.bashrc
source ~/.bashrc
```

### Windows (Quick Setup)

```batch
# Run the setup script
setup_env.bat

# Set your token (REQUIRED)
set MINIAGENT_TOKEN=your-shared-token-from-flutter
```

## 3. Verify Installation

```bash
# Check that sitecustomize loads
python -c "import sitecustomize; print('✓ Hook loaded')"

# Check PYTHONPATH
python -c "import sys; print('✓ PYTHONPATH OK' if '/home/mohamed/detector-rdpbridge' in str(sys.path) else '✗ PYTHONPATH missing')"

# Check token
python -c "import os; print('✓ Token set' if os.environ.get('MINIAGENT_TOKEN') else '✗ Token missing')"
```

## 4. Start Flutter App

Make sure your Flutter app is running with the local WebSocket server on port 8777.

## 5. Run a Test

```bash
cd /home/mohamed/detector-rdpbridge
python tests/test_chromium_timeout.py
```

Expected output:
```
Starting Chromium timeout test...
[INFO] Connecting to ws://127.0.0.1:8777/ws...
[INFO] WebSocket connected, sending hello...
[INFO] Handshake complete
Navigated to: https://example.com
Attempting to click non-existent button...
[INFO] Triggering support request: TimeoutError
[INFO] Sent support request: TimeoutError: click: locator('button:has-text("ThisButtonDoesNotExist")')
✓ Caught expected error: TimeoutError
✓ Browser still running after error
[INFO] Support request acknowledged: <requestId> (room: <roomId>)
✓ Test completed successfully
```

## 6. Run Your Own Playwright Scripts

No changes needed! Just run:

```bash
python my_playwright_script.py
```

The hook will automatically:
- Intercept errors
- Keep the browser running
- Send support requests to Flutter

## Troubleshooting

### "ModuleNotFoundError: No module named 'websocket'"
```bash
pip install websocket-client
```

### "Hook not loading"
Check PYTHONPATH:
```bash
echo $PYTHONPATH  # Linux/Mac
echo %PYTHONPATH%  # Windows
```

Should include `/home/mohamed/detector-rdpbridge`.

### "WebSocket connection failed"
1. Is Flutter running?
2. Is the local server on port 8777?
3. Does the token match?

### "NO_USER error"
Sign in to the Flutter app first.

### "BAD_AUTH error"
Token mismatch. Update `MINIAGENT_TOKEN` to match Flutter.

## Next Steps

- Read the full [README.md](README.md) for detailed configuration
- Run all smoke tests: `cd tests && for t in test_*.py; do python $t; done`
- Configure cooldown period: `export MINIAGENT_COOLDOWN_SEC=30`
- Enable URL redaction: `export MINIAGENT_REDACT_URLS=1`

## Disable the Hook

Temporarily:
```bash
export MINIAGENT_ENABLED=0
```

Permanently: remove from `~/.bashrc` or environment variables.


