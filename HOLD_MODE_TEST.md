# Hold Mode Test Guide

This guide walks you through testing the new hold mode functionality.

## What is Hold Mode?

Hold mode keeps your Playwright script alive when an error occurs, allowing an agent to:
1. Receive the support request
2. Connect to the browser
3. Fix the issue
4. Resume the script without restarting

## Prerequisites

1. Ensure the hook is installed:
```bash
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
export MINIAGENT_TOKEN="your-token"
export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"
```

2. Verify setup:
```bash
python verify_setup.py
```

## Test 1: Basic Hold Mode (Manual Resume)

This test demonstrates the script pausing on error and resuming via file signal.

### Terminal 1: Run the test script
```bash
# Enable hold mode
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume

# Clean up any existing resume file
rm -f /tmp/miniagent_resume

# Run test
python test_hold_mode.py
```

**Expected behavior:**
1. Browser launches
2. Navigates to example.com
3. Attempts to click non-existent button
4. Script pauses with message: "Holding on error (TimeoutError) - waiting for agent..."
5. Browser stays open
6. Support request sent to Flutter

### Terminal 2: Resume the script
While the script is paused:
```bash
# Create resume signal
touch /tmp/miniagent_resume
```

**Expected behavior:**
1. Script immediately continues
2. Logs: "Resume signal detected; continuing."
3. Navigates to playwright.dev
4. Completes successfully

## Test 2: Hold Mode with Timeout

This test demonstrates automatic resumption after a timeout.

### Run with timeout:
```bash
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_HOLD_SECS=10  # Resume after 10 seconds
rm -f /tmp/miniagent_resume

python test_hold_mode.py
```

**Expected behavior:**
1. Script pauses on error
2. Waits for 10 seconds
3. Logs: "Hold timeout reached; continuing."
4. Continues execution automatically

## Test 3: Swallow Mode

This test shows how errors can be ignored entirely.

### Run with swallow mode:
```bash
export MINIAGENT_ON_ERROR=swallow

python test_hold_mode.py
```

**Expected behavior:**
1. Error occurs
2. Support request sent
3. Script continues immediately (no pause, no exception)
4. Method returns None

## Test 4: Report Mode (Default)

This test confirms the original behavior still works.

### Run with report mode:
```bash
export MINIAGENT_ON_ERROR=report
# or unset it:
unset MINIAGENT_ON_ERROR

python test_hold_mode.py
```

**Expected behavior:**
1. Error occurs
2. Support request sent
3. Exception is re-raised
4. Script catches exception in try/except block

## Test 5: Use with Existing Scripts

Test with the example script (no modifications needed):

### Hold mode:
```bash
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
rm -f /tmp/miniagent_resume

python example_playwright_script.py

# In another terminal when paused:
touch /tmp/miniagent_resume
```

### Compare with report mode:
```bash
export MINIAGENT_ON_ERROR=report

python example_playwright_script.py
# Script will catch exceptions and continue
```

## Validation Checklist

- [ ] Hold mode pauses script on error
- [ ] Browser stays open during hold
- [ ] Support request is sent
- [ ] Script resumes on file signal
- [ ] Script resumes on timeout
- [ ] Swallow mode continues without raising
- [ ] Report mode re-raises exceptions
- [ ] No modifications to Playwright scripts needed
- [ ] Works with existing test scripts

## Troubleshooting

### Script doesn't pause in hold mode
Check environment:
```bash
echo $MINIAGENT_ON_ERROR  # Should be "hold"
```

### Script doesn't resume
Check resume file path:
```bash
echo $MINIAGENT_RESUME_FILE  # Should match the path you're touching
ls -la /tmp/miniagent_resume  # Should exist after touching
```

### Resume file persists
The hook automatically deletes the resume file after detecting it, but you can manually clean it:
```bash
rm -f /tmp/miniagent_resume
```

## Integration with Agent Workflow

1. **Error occurs** → Script holds, browser stays open
2. **Support request sent** → Flutter app receives notification
3. **Agent connects** → Uses CDP (Chromium) or Playwright connection
4. **Agent fixes issue** → Manipulates page to fix the problem
5. **Agent signals resume** → Triggers: `touch /tmp/miniagent_resume`
6. **Script continues** → Picks up where it left off

## Alternative Resume Mechanisms

The current implementation uses a file signal. Future enhancements could include:
- WebSocket command from Flutter
- HTTP endpoint
- Named pipe/FIFO
- Environment variable change detection
- Time-based conditions

For now, the file signal is simple, reliable, and works across all platforms.

## Test 6: HTTP Resume Endpoint (Optional)

This test demonstrates resuming via a local HTTP endpoint instead of touching the resume file.

### Setup
```bash
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_HOST=127.0.0.1
export MINIAGENT_RESUME_HTTP_PORT=8787
export MINIAGENT_RESUME_HTTP_TOKEN="strong-shared-secret"
rm -f /tmp/miniagent_resume
```

### Run the test
```bash
python test_hold_mode.py
```

### Resume via HTTP
While the script is paused:
```bash
curl -sS -X POST \
  http://127.0.0.1:8787/resume \
  -H "Authorization: Bearer $MINIAGENT_RESUME_HTTP_TOKEN"
```

**Expected behavior:**
1. Script immediately continues
2. Logs: "Resume signal detected; continuing."
3. Navigates to playwright.dev and completes




