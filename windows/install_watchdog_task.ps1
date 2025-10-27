# PowerShell script to install Playwright Watchdog as a Windows Scheduled Task
# Run as: powershell -ExecutionPolicy Bypass -File install_watchdog_task.ps1

param(
    [string]$PythonPath = "python.exe",
    [string]$WatchdogScript = "$PSScriptRoot\..\playwright_watchdog.py"
)

# Resolve absolute paths
$WatchdogScript = Resolve-Path $WatchdogScript

Write-Host "Installing Playwright Watchdog as Scheduled Task..."
Write-Host "Python: $PythonPath"
Write-Host "Script: $WatchdogScript"

# Task configuration
$TaskName = "PlaywrightWatchdog"
$TaskDescription = "Monitors Playwright test runs and logs lifecycle events with CDP support"

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Task '$TaskName' already exists. Removing..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$WatchdogScript`"" `
    -WorkingDirectory (Split-Path $WatchdogScript)

# Create task trigger (at logon)
$Trigger = New-ScheduledTaskTrigger -AtLogOn

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # No time limit

# Create task principal (current user)
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $TaskDescription `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Force

Write-Host ""
Write-Host "Scheduled Task installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the task now:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To view task status:"
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host ""
Write-Host "To remove the task:"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""

# Optionally start the task
$Start = Read-Host "Start the task now? (y/n)"
if ($Start -eq 'y' -or $Start -eq 'Y') {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Task started." -ForegroundColor Green
}


