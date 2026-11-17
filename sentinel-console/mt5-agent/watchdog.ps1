$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName "Sentinel-MT5-Agent" -ErrorAction SilentlyContinue
if ($null -eq $task) { exit 1 }
if ($task.State -ne "Running") {
    Start-ScheduledTask -TaskName "Sentinel-MT5-Agent"
}
