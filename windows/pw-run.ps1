# PowerShell wrapper for Playwright tests with watchdog integration
# Usage: .\pw-run.ps1 [playwright test arguments...]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$TestArgs
)

# Configuration
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$WatchdogDir = if ($env:PW_WATCHDOG_DIR) { $env:PW_WATCHDOG_DIR } else { Join-Path $env:USERPROFILE ".pw_watchdog" }
$ReportsDir = Join-Path $WatchdogDir "reports"

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null

# Generate runId
if ($env:PW_WATCHDOG_RUN_ID) {
    $RunId = $env:PW_WATCHDOG_RUN_ID
} else {
    $Timestamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
    $Pid = $PID
    $RunId = "$Timestamp-$Pid"
}

# Export environment
$env:PW_WATCHDOG_RUN_ID = $RunId
$env:PW_WATCHDOG_REPORT_FILE = Join-Path $ReportsDir "$RunId.json"
$env:PWDEBUG = "1"

# Add injector to NODE_OPTIONS
$InjectorPath = Join-Path $ProjectRoot "injectors\pw_injector.js"
$CurrentNodeOptions = if ($env:NODE_OPTIONS) { $env:NODE_OPTIONS } else { "" }
$env:NODE_OPTIONS = "--require `"$InjectorPath`" $CurrentNodeOptions"

Write-Host "Starting Playwright test with watchdog integration"
Write-Host "RunId: $RunId"
Write-Host "Report: $($env:PW_WATCHDOG_REPORT_FILE)"
Write-Host ""

# Run Playwright
$AllArgs = @("playwright", "test", "--reporter=json,line", "--trace=retain-on-failure") + $TestArgs
& npx @AllArgs

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "Test completed with exit code: $ExitCode"
Write-Host "Check watchdog logs: $(Join-Path $WatchdogDir 'logs\watchdog.jsonl')"

exit $ExitCode


