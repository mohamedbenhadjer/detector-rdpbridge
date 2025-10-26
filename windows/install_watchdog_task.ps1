$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot '..' 'playwright_watchdog.py' | Resolve-Path
$python = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $python) { throw 'Python not found in PATH' }

$action = New-ScheduledTaskAction -Execute $python.Source -Argument "`"$($scriptPath.Path)`" --verbose"
$trig = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$taskName = 'PlaywrightWatchdog'
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trig -Settings $settings -Force
Write-Host "Scheduled task '$taskName' installed."




