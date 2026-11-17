# Sentinel MT5 Windows persistent installation.
# Run in a Windows desktop session under the SAME user who is logged in to MT5 Demo.
$ErrorActionPreference = "Stop"
$TaskName = "Sentinel-MT5-Agent"
$WatchdogName = "Sentinel-MT5-Watchdog"
$PersistentRoot = Join-Path $env:LOCALAPPDATA "SentinelMT5\app"
$Config = Join-Path $env:LOCALAPPDATA "SentinelMT5\config.json"
if (!(Test-Path $Config)) { throw "Pair the agent first: py agent.py pair --url ... --code ..." }
New-Item -ItemType Directory -Force -Path $PersistentRoot | Out-Null
# Never schedule from Downloads or a temporary extracted ZIP folder.
foreach ($name in @("agent.py", "watchdog.ps1", "requirements.txt", "install_agent.ps1")) {
  $src = Join-Path $PSScriptRoot $name
  $dst = Join-Path $PersistentRoot $name
  if (!(Test-Path $src)) { throw "Missing $name in installer folder" }
  if ([IO.Path]::GetFullPath($src) -ne [IO.Path]::GetFullPath($dst)) {
    Copy-Item -LiteralPath $src -Destination $dst -Force
  }
}
$Agent = Join-Path $PersistentRoot "agent.py"
$Watchdog = Join-Path $PersistentRoot "watchdog.ps1"
$pythonLines = @(& py -3 -c "import sys; print(sys.executable)" 2>$null)
if ($LASTEXITCODE -ne 0 -or $pythonLines.Count -lt 1) { throw "Python 3 missing. Install Python and retry." }
$Python = [string]$pythonLines[0]
if (!(Test-Path $Python)) { throw "Python executable missing: $Python" }
& $Python -c "import MetaTrader5, keyring"
if ($LASTEXITCODE -ne 0) { throw "Dependencies missing: py -m pip install -r requirements.txt" }
$arguments = '"' + $Agent + '" run'
$action = New-ScheduledTaskAction -Execute $Python -Argument $arguments -WorkingDirectory $PersistentRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -RestartCount 100 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Sentinel MT5 demo connection agent" -Force | Out-Null
# Independent watchdog. Scheduled tasks are per-user and require interactive login for MT5 GUI.
$watchAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $Watchdog + '"') -WorkingDirectory $PersistentRoot
$watchTrigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1))
$watchTrigger.Repetition.Interval = "PT5M"
$watchTrigger.Repetition.Duration = "P3650D"
$watchSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable
Register-ScheduledTask -TaskName $WatchdogName -Action $watchAction -Trigger $watchTrigger -Settings $watchSettings -Principal $principal -Description "Restart Sentinel MT5 agent when it exits" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Write-Host "Sentinel MT5 agent installed in: $PersistentRoot" -ForegroundColor Green
Write-Host "Tasks: $TaskName / $WatchdogName"
Write-Host "Logs: $env:LOCALAPPDATA\SentinelMT5\agent.log"
Write-Host "Note: scheduled at USER LOGON, not before Windows sign-in."
