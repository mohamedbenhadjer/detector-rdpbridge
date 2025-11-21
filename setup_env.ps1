# Setup script for Windows PowerShell
#
# USAGE:
#
# 1. Ad-hoc (temporary, current session only):
#    . .\setup_env.ps1
#    (The dot at the beginning sources the script in the current session)
#
# 2. Persistent (automatic for all PowerShell sessions):
#    Add this line to your PowerShell profile ($PROFILE):
#      . "C:\absolute\path\to\detector-rdpbridge\setup_env.ps1"
#
#    To edit your profile:
#      notepad $PROFILE
#    (Create the file if it doesn't exist)
#
#    Or run this command once to append it automatically:
#      Add-Content $PROFILE ". `"$PSScriptRoot\setup_env.ps1`""
#
# After persistent setup, you never need to run this script manually again!

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$env:PYTHONPATH = "$ScriptDir;$env:PYTHONPATH"
$env:MINIAGENT_ENABLED = "1"
$env:MINIAGENT_WS_URL = "ws://127.0.0.1:8777/ws"
$env:MINIAGENT_CLIENT = "python-cdp-monitor"
$env:MINIAGENT_COOLDOWN_SEC = "0"
$env:MINIAGENT_RESUME_HTTP_TOKEN = "change-me"
$env:MINIAGENT_TOKEN = "change-me"
$env:MINIAGENT_DEBUG_PORT = "9222"
$env:MINIAGENT_FORCE_DEBUG_PORT = "1"
$env:MINIAGENT_ON_ERROR = "hold"
$env:MINIAGENT_RESUME_HTTP = "1"
$env:MINIAGENT_RESUME_FILE = "$env:TEMP\miniagent_resume"
$env:MINIAGENT_HOLD_SECS = "3600"

# IMPORTANT: Set your actual token here
if ($env:MINIAGENT_TOKEN -eq "change-me") {
    Write-Host "WARNING: MINIAGENT_TOKEN is not set!" -ForegroundColor Yellow
    Write-Host "Please set it before running Playwright tests:" -ForegroundColor Yellow
    Write-Host '  $env:MINIAGENT_TOKEN="your-shared-token-here"' -ForegroundColor Cyan
}

Write-Host "MiniAgent environment configured" -ForegroundColor Green
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host "MINIAGENT_ENABLED: $env:MINIAGENT_ENABLED"
Write-Host "MINIAGENT_WS_URL: $env:MINIAGENT_WS_URL"
Write-Host "MINIAGENT_ON_ERROR: $env:MINIAGENT_ON_ERROR"
Write-Host "MINIAGENT_HOLD_SECS: $env:MINIAGENT_HOLD_SECS"

