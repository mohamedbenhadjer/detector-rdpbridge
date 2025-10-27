# PowerShell wrapper for pytest with watchdog integration
# Usage: .\pw-run-pytest.ps1 [pytest arguments...]

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
$env:PW_WATCHDOG_REPORT_FILE = Join-Path $ReportsDir "$RunId.xml"
$env:PWDEBUG = "1"

# Add injector to PYTHONPATH
$InjectorPath = Join-Path $ProjectRoot "injectors\pw_py_inject"
$CurrentPythonPath = if ($env:PYTHONPATH) { $env:PYTHONPATH } else { "" }
$env:PYTHONPATH = if ($CurrentPythonPath) { "$InjectorPath;$CurrentPythonPath" } else { $InjectorPath }

# Add JUnit XML to PYTEST_ADDOPTS
$CurrentPytestOpts = if ($env:PYTEST_ADDOPTS) { $env:PYTEST_ADDOPTS } else { "" }
$env:PYTEST_ADDOPTS = "--junitxml=`"$($env:PW_WATCHDOG_REPORT_FILE)`" $CurrentPytestOpts"

Write-Host "Starting pytest with watchdog integration"
Write-Host "RunId: $RunId"
Write-Host "Report: $($env:PW_WATCHDOG_REPORT_FILE)"
Write-Host ""

# Run pytest
& pytest @TestArgs

$ExitCode = $LASTEXITCODE

Write-Host ""
Write-Host "Test completed with exit code: $ExitCode"
Write-Host "Check watchdog logs: $(Join-Path $WatchdogDir 'logs\watchdog.jsonl')"

exit $ExitCode


