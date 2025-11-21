#!/bin/bash
# Setup script for Linux/Mac
#
# USAGE:
#
# 1. Ad-hoc (temporary, current terminal only):
#    source setup_env.sh
#
# 2. Persistent (automatic for all terminals):
#    Add this line to your ~/.bashrc or ~/.zshrc:
#      source /absolute/path/to/detector-rdpbridge/setup_env.sh
#
#    Or run this command once to append it automatically:
#      echo "source $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/setup_env.sh" >> ~/.bashrc
#      source ~/.bashrc
#
# After persistent setup, you never need to run this script manually again!

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export MINIAGENT_ENABLED=1
export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"
export MINIAGENT_CLIENT="python-cdp-monitor"
export MINIAGENT_COOLDOWN_SEC=0
export MINIAGENT_RESUME_HTTP_TOKEN="change-me"
export MINIAGENT_TOKEN="change-me"
export MINIAGENT_DEBUG_PORT=9222
export MINIAGENT_FORCE_DEBUG_PORT=0
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_HOLD_SECS=3600

# IMPORTANT: Set your actual token here
if [ "$MINIAGENT_TOKEN" = "change-me" ]; then
    echo "WARNING: MINIAGENT_TOKEN is not set!"
    echo "Please set it before running Playwright tests:"
    echo "  export MINIAGENT_TOKEN=\"your-shared-token-here\""
fi

echo "MiniAgent environment configured"
echo "PYTHONPATH: $PYTHONPATH"
echo "MINIAGENT_ENABLED: $MINIAGENT_ENABLED"
echo "MINIAGENT_WS_URL: $MINIAGENT_WS_URL"


