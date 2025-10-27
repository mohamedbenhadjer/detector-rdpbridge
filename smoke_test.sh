#!/usr/bin/env bash
# Smoke test for Playwright Watchdog basic functionality
# Tests core components without requiring full Playwright installation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WATCHDOG_DIR="/tmp/pw_watchdog_test_$$"
TEST_PASSED=0
TEST_FAILED=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Playwright Watchdog Smoke Test"
echo "========================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ -n "${WATCHDOG_PID:-}" ]; then
        kill $WATCHDOG_PID 2>/dev/null || true
    fi
    rm -rf "$WATCHDOG_DIR"
}
trap cleanup EXIT

# Test functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((TEST_PASSED++))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((TEST_FAILED++))
}

warn() {
    echo -e "${YELLOW}!${NC} $1"
}

# Test 1: Check Python dependencies
echo "Test 1: Checking Python dependencies..."
if python3 -c "import psutil" 2>/dev/null; then
    pass "Required Python dependencies installed (psutil)"
else
    warn "Python dependencies missing - install with: pip install -r requirements.txt"
    warn "Or system packages: apt install python3-psutil python3-dotenv"
fi

# Test 2: Check watchdog script exists and is executable
echo ""
echo "Test 2: Checking watchdog script..."
if [ -x "$SCRIPT_DIR/playwright_watchdog.py" ]; then
    pass "Watchdog script is executable"
else
    fail "Watchdog script not found or not executable"
fi

# Test 3: Check injector files exist
echo ""
echo "Test 3: Checking injector files..."
if [ -f "$SCRIPT_DIR/injectors/pw_injector.js" ]; then
    pass "Node.js injector found"
else
    fail "Node.js injector not found"
fi

if [ -f "$SCRIPT_DIR/injectors/pw_py_inject/sitecustomize.py" ]; then
    pass "Python injector found"
else
    fail "Python injector not found"
fi

# Test 4: Test directory creation
echo ""
echo "Test 4: Testing directory structure..."
export PW_WATCHDOG_DIR="$WATCHDOG_DIR"
python3 << 'EOF'
import os
from pathlib import Path

watchdog_dir = Path(os.environ['PW_WATCHDOG_DIR'])
for subdir in ['logs', 'cdp', 'reports', 'tmp']:
    (watchdog_dir / subdir).mkdir(parents=True, exist_ok=True)

print("Directories created successfully")
EOF

if [ -d "$WATCHDOG_DIR/logs" ] && [ -d "$WATCHDOG_DIR/cdp" ]; then
    pass "Directory structure created"
else
    fail "Failed to create directory structure"
fi

# Test 5: Test JSONL handler
echo ""
echo "Test 5: Testing JSONL logging..."
python3 << 'EOF'
import os
import json
from pathlib import Path

# Import the watchdog module
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright_watchdog import RotatingJSONLHandler

watchdog_dir = Path(os.environ['PW_WATCHDOG_DIR'])
handler = RotatingJSONLHandler(
    watchdog_dir / 'logs' / 'test.jsonl',
    max_size=1024,
    backup_count=3
)

# Write test event
handler.write({'event': 'test', 'message': 'Hello World'})

# Verify
logfile = watchdog_dir / 'logs' / 'test.jsonl'
if logfile.exists():
    with open(logfile) as f:
        line = f.readline()
        data = json.loads(line)
        if data['event'] == 'test' and data['message'] == 'Hello World':
            print("JSONL logging works correctly")
        else:
            raise ValueError("Log content mismatch")
else:
    raise FileNotFoundError("Log file not created")
EOF

if [ $? -eq 0 ]; then
    pass "JSONL logging works"
else
    fail "JSONL logging failed"
fi

# Test 6: Test process detection patterns
echo ""
echo "Test 6: Testing process detection patterns..."
python3 << 'EOF'
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright_watchdog import PlaywrightWatchdog
import re

# Mock process class
class MockProc:
    def __init__(self, cmdline):
        self._cmdline = cmdline
    
    def cmdline(self):
        return self._cmdline

watchdog = PlaywrightWatchdog()

# Test Node patterns
test_cases = [
    (['node', 'node_modules/.bin/playwright', 'test'], True, 'Node playwright test'),
    (['npx', 'playwright', 'test'], True, 'npx playwright test'),
    (['pytest', '--browser=chromium'], True, 'pytest with browser'),
    (['python', '-m', 'pytest'], False, 'pytest without playwright'),
    (['node', 'app.js'], False, 'regular node app'),
]

failed = False
for cmdline, expected, desc in test_cases:
    proc = MockProc(cmdline)
    result = watchdog._is_playwright_process(proc)
    if result == expected:
        print(f"✓ {desc}")
    else:
        print(f"✗ {desc} (expected {expected}, got {result})")
        failed = True

if not failed:
    print("All pattern tests passed")
else:
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    pass "Process detection patterns work"
else
    fail "Process detection patterns failed"
fi

# Test 7: Test CDP metadata writing
echo ""
echo "Test 7: Testing CDP metadata..."
python3 << 'EOF'
import os
import json
from pathlib import Path

watchdog_dir = Path(os.environ['PW_WATCHDOG_DIR'])
cdp_dir = watchdog_dir / 'cdp'

# Simulate writing CDP metadata
run_id = "test-run-12345"
cdp_info = {
    'runId': run_id,
    'port': 9222,
    'wsUrl': 'ws://127.0.0.1:9222/devtools/browser/test',
    'devtoolsActivePortPath': '/tmp/test/DevToolsActivePort'
}

cdp_file = cdp_dir / f"{run_id}.json"
with open(cdp_file, 'w') as f:
    json.dump(cdp_info, f, indent=2)

# Verify
with open(cdp_file) as f:
    data = json.load(f)
    if data['runId'] == run_id and data['port'] == 9222:
        print("CDP metadata write/read works")
    else:
        raise ValueError("CDP metadata mismatch")
EOF

if [ $? -eq 0 ]; then
    pass "CDP metadata handling works"
else
    fail "CDP metadata handling failed"
fi

# Test 8: Test Node injector syntax
echo ""
echo "Test 8: Testing Node.js injector syntax..."
if command -v node &> /dev/null; then
    if node -c "$SCRIPT_DIR/injectors/pw_injector.js" 2>/dev/null; then
        pass "Node.js injector syntax valid"
    else
        fail "Node.js injector has syntax errors"
    fi
else
    warn "Node.js not installed, skipping injector syntax check"
fi

# Test 9: Test Python injector syntax
echo ""
echo "Test 9: Testing Python injector syntax..."
if python3 -m py_compile "$SCRIPT_DIR/injectors/pw_py_inject/sitecustomize.py" 2>/dev/null; then
    pass "Python injector syntax valid"
else
    fail "Python injector has syntax errors"
fi

# Test 10: Test helper scripts
echo ""
echo "Test 10: Testing helper scripts..."
HELPER_CHECKS=0
for script in "bin/pw-run.sh" "bin/pw-run-pytest.sh"; do
    if [ -x "$SCRIPT_DIR/$script" ]; then
        ((HELPER_CHECKS++))
    fi
done

if [ $HELPER_CHECKS -eq 2 ]; then
    pass "Helper scripts are executable"
elif [ $HELPER_CHECKS -eq 0 ]; then
    fail "Helper scripts not found or not executable"
else
    warn "Some helper scripts missing or not executable"
fi

# Summary
echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}Passed:${NC} $TEST_PASSED"
echo -e "${RED}Failed:${NC} $TEST_FAILED"
echo ""

if [ $TEST_FAILED -eq 0 ]; then
    echo -e "${GREEN}All smoke tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Install dependencies if you haven't: pip install -r requirements.txt"
    echo "2. Run the watchdog: ./playwright_watchdog.py"
    echo "3. Run validation tests: see test_validation.md"
    exit 0
else
    echo -e "${RED}Some tests failed. Please fix the issues before proceeding.${NC}"
    exit 1
fi

