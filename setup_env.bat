@echo off
REM Setup script for Windows
REM Run this before executing Playwright tests, or add to system environment variables

set SCRIPT_DIR=%~dp0

set PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%
set MINIAGENT_ENABLED=1
set MINIAGENT_WS_URL=ws://127.0.0.1:8777/ws
set MINIAGENT_CLIENT=python-cdp-monitor
set MINIAGENT_COOLDOWN_SEC=20

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


