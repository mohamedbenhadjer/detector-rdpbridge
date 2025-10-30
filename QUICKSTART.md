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

## 3. Configure Error Handling Mode (Optional)

Choose how Playwright errors are handled:

### Report Mode (Default)
Sends support requests but re-raises exceptions (script exits on error):
```bash
export MINIAGENT_ON_ERROR=report  # or leave unset
```

### Hold Mode (Recommended for Agent Intervention)
Keeps the script alive when errors occur, waiting for the agent to fix the issue:
```bash
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
# Optional: auto-resume after timeout instead of waiting forever
export MINIAGENT_HOLD_SECS=3600  # or "forever"/"inf" for no timeout
```

When an error occurs in hold mode:
1. Browser stays open
2. Support request is sent to Flutter
3. Script pauses and waits
4. Agent fixes the issue
5. Resume the script: `touch /tmp/miniagent_resume` (or use the optional HTTP endpoint below)

#### Optional: Resume via HTTP endpoint

Enable a local HTTP endpoint the agent can call to resume automatically:

```bash
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_HOST=127.0.0.1
export MINIAGENT_RESUME_HTTP_PORT=8787
export MINIAGENT_RESUME_HTTP_TOKEN="strong-shared-secret"
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
```

Agent call example:

```bash
curl -sS -X POST \
  http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer $MINIAGENT_RESUME_HTTP_TOKEN"
```

### Swallow Mode
Ignores errors and continues (returns None for failed actions):
```bash
export MINIAGENT_ON_ERROR=swallow
```

## 4. Verify Installation

```bash
# Check that sitecustomize loads
python -c "import sitecustomize; print('✓ Hook loaded')"

# Check PYTHONPATH
python -c "import sys; print('✓ PYTHONPATH OK' if '/home/mohamed/detector-rdpbridge' in str(sys.path) else '✗ PYTHONPATH missing')"

# Check token
python -c "import os; print('✓ Token set' if os.environ.get('MINIAGENT_TOKEN') else '✗ Token missing')"
```

## 5. Start Flutter App

Make sure your Flutter app is running with the local WebSocket server on port 8777.

## 6. Run a Test

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

## 7. Run Your Own Playwright Scripts

No changes needed! Just run:

```bash
python my_playwright_script.py
```

The hook will automatically:
- Intercept errors
- Keep the browser running (in hold mode)
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

### Script is stuck/paused after an error
You're in hold mode. The script is waiting for the agent to fix the issue.
- Check the Flutter app for the support request
- After fixing, resume: `touch /tmp/miniagent_resume`
- Or switch to report mode: `export MINIAGENT_ON_ERROR=report`

## Next Steps

- Read the full [README.md](README.md) for detailed configuration
- Run all smoke tests: `cd tests && for t in test_*.py; do python $t; done`
- Configure cooldown period: `export MINIAGENT_COOLDOWN_SEC=30`
- Enable URL redaction: `export MINIAGENT_REDACT_URLS=1`
- Try hold mode: `export MINIAGENT_ON_ERROR=hold` for agent-assisted debugging

## Disable the Hook

Temporarily:
```bash
export MINIAGENT_ENABLED=0
```

Permanently: remove from `~/.bashrc` or environment variables.



