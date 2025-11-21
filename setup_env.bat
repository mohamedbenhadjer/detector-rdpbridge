@echo off
REM Setup script for Windows CMD
REM
REM USAGE:
REM
REM 1. Ad-hoc (temporary, current CMD window only):
REM    setup_env.bat
REM
REM 2. Persistent (permanent for all future CMD sessions):
REM    setup_env.bat install
REM    This uses 'setx' to write environment variables permanently.
REM    After running, close and reopen CMD windows for changes to take effect.
REM
REM After persistent setup, you never need to run this script manually again!

set SCRIPT_DIR=%~dp0

REM Check if install mode is requested
if /I "%1"=="install" goto INSTALL_MODE

REM === TEMPORARY MODE (current session only) ===
:TEMP_MODE
set PYTHONPATH=%SCRIPT_DIR%;%PYTHONPATH%
set MINIAGENT_ENABLED=1
set MINIAGENT_WS_URL=ws://127.0.0.1:8777/ws
set MINIAGENT_CLIENT=python-cdp-monitor
set MINIAGENT_COOLDOWN_SEC=0
set MINIAGENT_RESUME_HTTP_TOKEN=change-me
set MINIAGENT_TOKEN=change-me
set MINIAGENT_DEBUG_PORT=9222
set MINIAGENT_FORCE_DEBUG_PORT=1
set MINIAGENT_ON_ERROR=hold
set MINIAGENT_RESUME_HTTP=1
set MINIAGENT_RESUME_FILE=%TEMP%\miniagent_resume
set MINIAGENT_HOLD_SECS=3600

REM IMPORTANT: Set your actual token here
if "%MINIAGENT_TOKEN%"=="change-me" (
    echo WARNING: MINIAGENT_TOKEN is not set!
    echo Please set it before running Playwright tests:
    echo   set MINIAGENT_TOKEN=your-shared-token-here
)

echo MiniAgent environment configured (temporary - current session only)
echo PYTHONPATH: %PYTHONPATH%
echo MINIAGENT_ENABLED: %MINIAGENT_ENABLED%
echo MINIAGENT_WS_URL: %MINIAGENT_WS_URL%
goto END

REM === INSTALL MODE (permanent for all sessions) ===
:INSTALL_MODE
echo Installing MiniAgent environment variables permanently...
echo.
echo IMPORTANT: You must set MINIAGENT_TOKEN manually after installation:
echo   setx MINIAGENT_TOKEN "your-actual-token-here"
echo.

REM Get current PYTHONPATH to merge with new value
set CURRENT_PYTHONPATH=%PYTHONPATH%
if defined CURRENT_PYTHONPATH (
    setx PYTHONPATH "%SCRIPT_DIR%;%CURRENT_PYTHONPATH%"
) else (
    setx PYTHONPATH "%SCRIPT_DIR%"
)

setx MINIAGENT_ENABLED "1"
setx MINIAGENT_WS_URL "ws://127.0.0.1:8777/ws"
setx MINIAGENT_CLIENT "python-cdp-monitor"
setx MINIAGENT_COOLDOWN_SEC "0"
setx MINIAGENT_DEBUG_PORT "9222"
setx MINIAGENT_FORCE_DEBUG_PORT "1"
setx MINIAGENT_ON_ERROR "hold"
setx MINIAGENT_RESUME_HTTP "1"
setx MINIAGENT_RESUME_HTTP_TOKEN "change-me"
setx MINIAGENT_HOLD_SECS "3600"

REM Note: MINIAGENT_RESUME_FILE can't use %TEMP% in setx, use literal path
setx MINIAGENT_RESUME_FILE "%USERPROFILE%\AppData\Local\Temp\miniagent_resume"

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo IMPORTANT NEXT STEPS:
echo 1. Set your actual tokens (required):
echo    setx MINIAGENT_TOKEN "your-actual-token-here"
echo    setx MINIAGENT_RESUME_HTTP_TOKEN "your-actual-token-here"
echo.
echo 2. Close this CMD window and open a new one for changes to take effect.
echo.
echo After this, environment variables will be set automatically in all CMD sessions.
echo You never need to run this script again!
echo.
goto END

:END


