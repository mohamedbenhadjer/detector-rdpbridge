#!/usr/bin/env bash
# Playwright Run Helper for Python/pytest projects
# Wraps pytest invocation with watchdog integration

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
export PW_WATCHDOG_REPORT_FILE="$REPORTS_DIR/$RUNID.xml"
export PWDEBUG=1
export PYTHONPATH="$PROJECT_ROOT/injectors/pw_py_inject:${PYTHONPATH:-}"
export PYTEST_ADDOPTS="--junitxml=$PW_WATCHDOG_REPORT_FILE ${PYTEST_ADDOPTS:-}"

echo "Starting pytest with watchdog integration"
echo "RunId: $RUNID"
echo "Report: $PW_WATCHDOG_REPORT_FILE"
echo ""

# Run pytest
pytest "$@"

EXIT_CODE=$?

echo ""
echo "Test completed with exit code: $EXIT_CODE"
echo "Check watchdog logs: $WATCHDOG_DIR/logs/watchdog.jsonl"

exit $EXIT_CODE


