#!/usr/bin/env bash
# Playwright Run Helper for Node.js projects
# Wraps Playwright test invocation with watchdog integration

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WATCHDOG_DIR="${PW_WATCHDOG_DIR:-$HOME/.pw_watchdog}"
REPORTS_DIR="$WATCHDOG_DIR/reports"

# Ensure directories exist
mkdir -p "$REPORTS_DIR"

# Generate runId
RUNID="${PW_WATCHDOG_RUN_ID:-$(date +%s%3N)-$$}"

# Export environment
export PW_WATCHDOG_RUN_ID="$RUNID"
export PW_WATCHDOG_REPORT_FILE="$REPORTS_DIR/$RUNID.json"
export PWDEBUG=1
export NODE_OPTIONS="--require $PROJECT_ROOT/injectors/pw_injector.js ${NODE_OPTIONS:-}"

echo "Starting Playwright test with watchdog integration"
echo "RunId: $RUNID"
echo "Report: $PW_WATCHDOG_REPORT_FILE"
echo ""

# Run Playwright with appropriate flags
npx playwright test \
    --reporter=json,line \
    --trace=retain-on-failure \
    "$@"

EXIT_CODE=$?

echo ""
echo "Test completed with exit code: $EXIT_CODE"
echo "Check watchdog logs: $WATCHDOG_DIR/logs/watchdog.jsonl"

exit $EXIT_CODE


