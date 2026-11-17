param(
  [Parameter(Mandatory=$true)][string]$Code,
  [string]$ConsoleUrl = "https://sentinel-mt5-console.vercel.app",
  [string]$MT5Path = ""
)
$ErrorActionPreference="Stop"
$base="https://raw.githubusercontent.com/nfliex9-crypto/Bot/sentinel-console-isolated-v1/sentinel-console/mt5-agent"
$dir=Join-Path $env:LOCALAPPDATA "SentinelMT5\package"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
foreach($name in @("agent.py","requirements.txt","install_agent.ps1","watchdog.ps1")){
 $output=Join-Path $dir $name
 Invoke-WebRequest -Uri "$base/$name" -OutFile $output -UseBasicParsing
 if(!(Test-Path $output)){throw "Download failed for $name"}
}
$python = (& py -3 -c "import sys;print(sys.executable)" 2>$null | Select-Object -First 1)
if(-not $python){throw "Python 3 is required: https://www.python.org/downloads/windows/"}
& $python -m pip install -r (Join-Path $dir "requirements.txt")
if($LASTEXITCODE -ne 0){throw "Python dependencies failed to install"}
$arguments=@((Join-Path $dir "agent.py"),"pair","--url",$ConsoleUrl,"--code",$Code)
if($MT5Path){$arguments+=@("--mt5-path",$MT5Path)}
& $python @arguments
if($LASTEXITCODE -ne 0){throw "Agent pairing failed"}
& (Join-Path $dir "install_agent.ps1")
if(-not $?){throw "Autostart task failed"}
Write-Host "Sentinel MT5 agent installed. Keep MT5 logged into a DEMO account." -ForegroundColor Green
Write-Host "Log file: $env:LOCALAPPDATA\SentinelMT5\agent.log"
