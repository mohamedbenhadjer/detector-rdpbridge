#!/bin/bash
# Setup script for Linux/Mac
# Source this file or add contents to your ~/.bashrc or ~/.zshrc

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
export MINIAGENT_ENABLED=1
export MINIAGENT_WS_URL="ws://127.0.0.1:8777/ws"
export MINIAGENT_CLIENT="python-cdp-monitor"
export MINIAGENT_COOLDOWN_SEC=0
export MINIAGENT_DEBUG_PORT=9222
export MINIAGENT_FORCE_DEBUG_PORT=1
export PYTHONPATH="/home/mohamed/detector-rdpbridge:$PYTHONPATH"
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_HTTP=1
export MINIAGENT_RESUME_HTTP_TOKEN="change-me"
export MINIAGENT_TOKEN="change-me"
export MINIAGENT_ON_ERROR=hold
export MINIAGENT_RESUME_FILE=/tmp/miniagent_resume
export MINIAGENT_HOLD_SECS=3600 

# IMPORTANT: Set your actual token here
if [ -z "$MINIAGENT_TOKEN" ]; then
    echo "WARNING: MINIAGENT_TOKEN is not set!"
    echo "Please set it before running Playwright tests:"
    echo "  export MINIAGENT_TOKEN=\"your-shared-token-here\""
fi

echo "MiniAgent environment configured"
echo "PYTHONPATH: $PYTHONPATH"
echo "MINIAGENT_ENABLED: $MINIAGENT_ENABLED"
echo "MINIAGENT_WS_URL: $MINIAGENT_WS_URL"


