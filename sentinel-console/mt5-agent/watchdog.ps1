# Sentinel MT5 independent Windows watchdog.
# Restarts a crashed agent. For a frozen agent, verifies PID and executable before killing its process tree.
$ErrorActionPreference = "Stop"
$TaskName = "Sentinel-MT5-Agent"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) { exit 1 }
if ($task.State -ne "Running") {
  Start-ScheduledTask -TaskName $TaskName
  exit 0
}
$markerPath = Join-Path $env:LOCALAPPDATA "SentinelMT5\loop.heartbeat.json"
if (!(Test-Path $markerPath)) { exit 0 }
$age = ((Get-Date) - (Get-Item $markerPath).LastWriteTime).TotalSeconds
if ($age -le 180) { exit 0 }
try {
  $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json
  $agentPid = [int]$marker.pid
  if ($agentPid -lt 1) { exit 0 }
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $agentPid" -ErrorAction Stop
  $expected = Join-Path $env:LOCALAPPDATA "SentinelMT5\app\agent.py"
  if ($null -eq $proc -or $proc.CommandLine -notmatch [regex]::Escape($expected)) {
    Write-Warning "Stale heartbeat, but agent PID identity cannot be verified. Not killing any process."
    exit 0
  }
  Write-Warning "MT5 agent frozen for $([int]$age)s; restarting verified process tree."
  & taskkill.exe /PID $agentPid /T /F | Out-Null
  Start-Sleep -Seconds 3
  $task = Get-ScheduledTask -TaskName $TaskName
  if ($task.State -ne "Running") { Start-ScheduledTask -TaskName $TaskName }
} catch {
  Write-Warning "Watchdog could not safely recover frozen agent: $_"
  exit 1
}
