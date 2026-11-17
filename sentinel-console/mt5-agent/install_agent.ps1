# Sentinel MT5 Windows Scheduled Task setup
# Run as the Windows user who has MetaTrader 5 installed and logged in to a Demo account.
$ErrorActionPreference = "Stop"
$TaskName = "Sentinel-MT5-Agent"
$WatchdogName = "Sentinel-MT5-Watchdog"
$Agent = Join-Path $PSScriptRoot "agent.py"
$Watchdog = Join-Path $PSScriptRoot "watchdog.ps1"
$Config = Join-Path $env:LOCALAPPDATA "SentinelMT5\config.json"
if (!(Test-Path $Config)) { throw "Pair the agent first: py agent.py pair --url ... --code ..." }
if (!(Test-Path $Agent)) { throw "agent.py not found" }
$Python = (& py -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1).Trim()
if (!$Python -or !(Test-Path $Python)) { throw "Python 3 not found. Install Python 3 and try again." }
# Verify dependencies before scheduling the task.
& $Python -c "import MetaTrader5, keyring" 2>$null
if ($LASTEXITCODE -ne 0) { throw "Dependencies missing. Run: py -m pip install -r requirements.txt" }
$arguments = '"' + $Agent + '" run'
$action = New-ScheduledTaskAction -Execute $Python -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Sentinel MT5 demo heartbeat, reconnect and local process supervision" -Force | Out-Null

# Separate watchdog every 5 minutes: if agent unexpectedly exits or is disabled after reboot,
# it starts the registered agent task; MultipleInstances=IgnoreNew prevents duplicate agents.
$watchAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $Watchdog + '"') -WorkingDirectory $PSScriptRoot
$watchTrigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1))
$watchTrigger.Repetition.Interval = "PT5M"
$watchTrigger.Repetition.Duration = "P3650D"
$watchSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $WatchdogName -Action $watchAction -Trigger $watchTrigger -Settings $watchSettings -Principal $principal -Description "Re-start Sentinel MT5 agent if no longer running" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Sentinel MT5 agent scheduled and launched." -ForegroundColor Green
Write-Host "Agent: $TaskName"
Write-Host "Watchdog: $WatchdogName"
Write-Host "Logs: $env:LOCALAPPDATA\SentinelMT5\agent.log"
Write-Host "Reminder: MT5 is a desktop terminal. Keep the Windows user session logged in on an always-on Windows VPS."
