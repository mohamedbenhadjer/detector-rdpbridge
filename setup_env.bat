@echo off
REM Setup script for Windows
REM Run this before executing Playwright tests, or add to system environment variables

set SCRIPT_DIR=%~dp0

set PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%
set MINIAGENT_ENABLED=1
set MINIAGENT_WS_URL=ws://127.0.0.1:8777/ws
set MINIAGENT_CLIENT=python-cdp-monitor
set MINIAGENT_COOLDOWN_SEC=0
set MINIAGENT_RESUME_HTTP_TOKEN="change-me"
set MINIAGENT_TOKEN="change-me"
set MINIAGENT_DEBUG_PORT=9222
set MINIAGENT_FORCE_DEBUG_PORT=1
set MINIAGENT_ON_ERROR=hold
set MINIAGENT_RESUME_HTTP=1
set MINIAGENT_RESUME_FILE=%TEMP%\miniagent_resume
set MINIAGENT_HOLD_SECS=3600 

REM IMPORTANT: Set your actual token here
if not defined MINIAGENT_TOKEN (
    echo WARNING: MINIAGENT_TOKEN is not set!
    echo Please set it before running Playwright tests:
    echo   set MINIAGENT_TOKEN=your-shared-token-here
)

echo MiniAgent environment configured
echo PYTHONPATH: %PYTHONPATH%
echo MINIAGENT_ENABLED: %MINIAGENT_ENABLED%
echo MINIAGENT_WS_URL: %MINIAGENT_WS_URL%


