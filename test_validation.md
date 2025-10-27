# Validation Test Plan

This document outlines the validation matrix for the Playwright Watchdog system.

## Test Matrix

### Environment Coverage

- [ ] Linux (Ubuntu/Debian)
- [ ] Linux (RHEL/CentOS)
- [ ] macOS
- [ ] Windows 10/11

### Test Runner Coverage

- [ ] Node.js - Playwright Test (npx playwright test)
- [ ] Node.js - Playwright Test (with package.json script)
- [ ] Python - pytest with pytest-playwright
- [ ] Python - pytest with custom fixtures

### Browser Coverage

- [ ] Chromium (primary target)
- [ ] Firefox (should not inject CDP)
- [ ] WebKit (should not inject CDP)

## Test Cases

### 1. Basic Process Detection

**Node.js:**
```bash
# Start watchdog in one terminal
./playwright_watchdog.py

# In another terminal, run a simple test
npx playwright test --grep "basic"

# Expected:
# - playwright_started event logged
# - playwright_succeeded or playwright_failed event logged
# - runId matches between events
```

**Python:**
```bash
# Start watchdog
./playwright_watchdog.py

# Run pytest
pytest tests/test_basic.py

# Expected: Same as above
```

**Validation:**
- [ ] Process detected and logged
- [ ] Correct pid, cmdline, cwd captured
- [ ] Exit code matches actual result

### 2. CDP Injection and Discovery

**Node.js:**
```bash
./bin/pw-run.sh --grep "simple"

# Check CDP metadata was written
cat ~/.pw_watchdog/cdp/*.json

# Expected:
# - port, wsUrl, devtoolsActivePortPath present
# - CDP WebSocket URL is valid
```

**Python:**
```bash
./bin/pw-run-pytest.sh -k "test_simple"

# Check CDP metadata
cat ~/.pw_watchdog/cdp/*.json

# Expected: Same as above
```

**Validation:**
- [ ] CDP metadata file created
- [ ] WebSocket URL format correct
- [ ] Port is ephemeral (not hardcoded)
- [ ] DevToolsActivePort file path exists
- [ ] Browser launches in headful mode

### 3. Failure Handling

**Node.js:**
```bash
# Create a test that fails
# tests/fail.spec.js:
# test('should fail', async ({ page }) => {
#   expect(true).toBe(false);
# });

./bin/pw-run.sh tests/fail.spec.js

# Expected:
# - Browser stays open (PWDEBUG=1)
# - playwright_failed event with error details
# - Trace file path in artifacts
```

**Python:**
```bash
# Create a test that fails
# tests/test_fail.py:
# def test_fail(page):
#     assert False

./bin/pw-run-pytest.sh tests/test_fail.py

# Expected:
# - Browser stays open
# - playwright_failed event
# - JUnit XML report parsed
```

**Validation:**
- [ ] Browser remains open after failure
- [ ] Exit code non-zero
- [ ] Error summary extracted (title, message)
- [ ] Trace/screenshot paths logged
- [ ] CDP still accessible

### 4. Success Handling

**Node.js:**
```bash
./bin/pw-run.sh --grep "passing"

# Expected:
# - playwright_succeeded event
# - exitCode: 0
# - No error field
```

**Python:**
```bash
./bin/pw-run-pytest.sh -k "test_pass"

# Expected: Same as above
```

**Validation:**
- [ ] Exit code is 0
- [ ] Success event logged
- [ ] Duration calculated correctly
- [ ] Report file path present

### 5. Artifact Correlation

**Node.js with Trace:**
```bash
./bin/pw-run.sh --trace=on

# Expected:
# - artifacts.traces array populated
# - Trace files exist at reported paths
```

**Node.js with Screenshots:**
```bash
# Test that takes screenshots
./bin/pw-run.sh tests/screenshot.spec.js

# Expected:
# - artifacts.screenshots array populated
```

**Validation:**
- [ ] Trace paths extracted from JSON report
- [ ] Screenshot paths extracted
- [ ] Files exist at reported locations
- [ ] Paths are absolute or relative to project root

### 6. Concurrent Runs

```bash
# Terminal 1
./bin/pw-run.sh --grep "test1" &

# Terminal 2
./bin/pw-run.sh --grep "test2" &

# Wait for both to complete
wait

# Expected:
# - Two distinct runIds
# - Two CDP metadata files
# - No collision in logs
# - All events properly correlated by runId
```

**Validation:**
- [ ] Unique runIds generated
- [ ] No log corruption
- [ ] CDP files don't overwrite each other
- [ ] Events properly correlated

### 7. Service Mode (Linux)

```bash
# Install service
systemctl --user enable --now pw-watchdog

# Run test
./bin/pw-run.sh

# Check journal
journalctl --user -u pw-watchdog -n 50

# Expected:
# - Service running
# - Events logged to journal and JSONL
```

**Validation:**
- [ ] Service starts on boot
- [ ] Logs to systemd journal
- [ ] JSONL file also updated
- [ ] Service restarts on crash

### 8. Service Mode (Windows)

```powershell
# Install task
.\windows\install_watchdog_task.ps1

# Start task
Start-ScheduledTask -TaskName "PlaywrightWatchdog"

# Run test
.\windows\pw-run.ps1

# Check logs
Get-Content ~/.pw_watchdog/logs/watchdog.jsonl -Tail 20
```

**Validation:**
- [ ] Task installed successfully
- [ ] Task starts on logon
- [ ] Logs written to JSONL
- [ ] WMI events captured (not polling)

### 9. Custom runId

```bash
export PW_WATCHDOG_RUN_ID="custom-test-run-123"
./bin/pw-run.sh

# Expected:
# - Events use "custom-test-run-123" as runId
# - CDP file named "custom-test-run-123.json"
```

**Validation:**
- [ ] Custom runId respected
- [ ] No auto-generation
- [ ] All artifacts use custom ID

### 10. Log Rotation

```bash
# Force large log file
for i in {1..1000}; do
  ./bin/pw-run.sh --grep "quick"
done

# Check log files
ls -lh ~/.pw_watchdog/logs/

# Expected:
# - watchdog.jsonl stays under max size
# - Backup files created (.jsonl.1, .jsonl.2, etc.)
# - Old backups removed when limit reached
```

**Validation:**
- [ ] Rotation triggers at configured size
- [ ] Backup files numbered correctly
- [ ] Old backups purged
- [ ] No data loss during rotation

### 11. CDP Connection Test

**Node.js:**
```javascript
// connect_cdp.js
const CDP = require('chrome-remote-interface');
const fs = require('fs');

async function test() {
  // Read CDP info from latest run
  const files = fs.readdirSync(process.env.HOME + '/.pw_watchdog/cdp/');
  const latest = files.sort().pop();
  const cdpInfo = JSON.parse(fs.readFileSync(
    `${process.env.HOME}/.pw_watchdog/cdp/${latest}`
  ));
  
  console.log('Connecting to:', cdpInfo.wsUrl);
  const client = await CDP({ target: cdpInfo.wsUrl });
  
  const { Page } = client;
  await Page.enable();
  
  const screenshot = await Page.captureScreenshot();
  fs.writeFileSync('cdp_test.png', screenshot.data, 'base64');
  
  console.log('Screenshot saved to cdp_test.png');
  await client.close();
}

test().catch(console.error);
```

**Validation:**
- [ ] CDP connection succeeds
- [ ] Can execute DevTools commands
- [ ] Screenshot captured successfully

### 12. Environment Variable Overrides

```bash
export PW_WATCHDOG_DIR=/tmp/test_watchdog
export PW_WATCHDOG_POLL_INTERVAL=1.0
export PW_WATCHDOG_STDOUT=0

./playwright_watchdog.py &
WATCHDOG_PID=$!

./bin/pw-run.sh

# Check custom directory
ls /tmp/test_watchdog/logs/

# Stop watchdog
kill $WATCHDOG_PID
```

**Validation:**
- [ ] Custom directory used
- [ ] Poll interval respected
- [ ] Stdout logging disabled
- [ ] All env vars honored

## Performance Benchmarks

### Polling Mode Overhead

```bash
# Run 100 quick tests and measure overhead
time for i in {1..100}; do
  npx playwright test --grep "instant"
done

# Compare with watchdog running vs not running
```

**Expected:**
- [ ] < 1% CPU usage for watchdog
- [ ] < 50MB memory usage
- [ ] Negligible impact on test execution time

### WMI Mode (Windows)

**Expected:**
- [ ] < 0.5% CPU usage
- [ ] < 30MB memory usage
- [ ] Event-driven (no polling overhead)

## Edge Cases

### 1. Chromium with --remote-debugging-pipe

```bash
# Test with pipe instead of port
# Should be overridden by injector
```

**Validation:**
- [ ] Injector adds --remote-debugging-port anyway
- [ ] CDP still accessible via network

### 2. Multiple Browser Instances

```bash
# Test that launches multiple browsers
./bin/pw-run.sh tests/multi_browser.spec.js

# Expected:
# - CDP info for first browser captured
# - No errors from multiple launches
```

**Validation:**
- [ ] No crashes
- [ ] At least one CDP connection available

### 3. Test Timeout/Hang

```bash
# Test that hangs
timeout 30s ./bin/pw-run.sh tests/hang.spec.js || true

# Expected:
# - Process exit captured
# - Exit code reflects timeout
```

**Validation:**
- [ ] Exit event logged
- [ ] Non-zero exit code
- [ ] No watchdog crash

### 4. Rapid Start/Stop

```bash
# Start and immediately stop
for i in {1..10}; do
  timeout 1s npx playwright test &
done
wait

# Expected:
# - No crashes
# - All starts/exits logged
# - Some may not have CDP info (race condition acceptable)
```

**Validation:**
- [ ] Watchdog remains stable
- [ ] No log corruption
- [ ] Events properly paired

## Success Criteria

### Must Have (P0)
- [ ] All basic detection tests pass on Linux and Windows
- [ ] CDP injection works for Node.js and Python
- [ ] Failure handling preserves browser and CDP
- [ ] Success cases log correctly
- [ ] No false positives/negatives in detection

### Should Have (P1)
- [ ] Concurrent runs work without collision
- [ ] Service mode operational on both platforms
- [ ] Log rotation works correctly
- [ ] Artifact paths extracted accurately

### Nice to Have (P2)
- [ ] Performance overhead acceptable
- [ ] All edge cases handled gracefully
- [ ] Custom environment variables work
- [ ] CDP connection from external tools verified

## Test Environment Setup

### Minimal Test Project (Node.js)

```bash
mkdir -p /tmp/pw-test-node
cd /tmp/pw-test-node
npm init -y
npm install -D @playwright/test
npx playwright install chromium

# Create simple test
cat > tests/example.spec.js << 'EOF'
const { test, expect } = require('@playwright/test');

test('pass', async ({ page }) => {
  await page.goto('https://example.com');
  expect(true).toBe(true);
});

test('fail', async ({ page }) => {
  await page.goto('https://example.com');
  expect(true).toBe(false);
});
EOF
```

### Minimal Test Project (Python)

```bash
mkdir -p /tmp/pw-test-py
cd /tmp/pw-test-py
python3 -m venv venv
source venv/bin/activate
pip install pytest pytest-playwright
playwright install chromium

# Create simple test
cat > tests/test_example.py << 'EOF'
def test_pass(page):
    page.goto('https://example.com')
    assert True

def test_fail(page):
    page.goto('https://example.com')
    assert False
EOF
```

## Reporting

After running validation:

1. Update this file with checkmarks for passing tests
2. Create GitHub issues for any failures
3. Document any platform-specific quirks
4. Update README with known limitations

---

**Last Updated:** 2025-10-26  
**Status:** Ready for validation


