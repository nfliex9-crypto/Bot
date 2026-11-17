# Sentinel MT5 — Windows Demo Agent (v1)

Sentinel uses two separate Vercel deployments and one persistent Neon Postgres database:

- **Console:** https://sentinel-mt5-console.vercel.app — protected owner dashboard, pairing-code generation, agent telemetry and revoke.
- **Agent bridge:** https://sentinel-mt5-bridge.vercel.app — public HTTPS endpoint for *claim* and *heartbeat only*. It has no order, admin, or trade endpoints.
- **Windows agent:** connects only to an MT5 terminal already signed in to a **Demo** account. It uploads status to the bridge every 20s. It NEVER requests or uploads broker passwords.

## Quick install on Windows

Prerequisites: Windows 10/11 or Windows Server, Python 3 (via `py -3`), MetaTrader 5 terminal installed and signed into a **Demo** account. Keep the MT5 desktop session running.

1. Open the Console → **ربط حساب MT5** → **ربط حساب MT5**. Generate a one-time pairing code (expires in 15 minutes).
2. On the same Windows machine, run in PowerShell:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/nfliex9-crypto/Bot/sentinel-console-isolated-v1/sentinel-console/mt5-agent/bootstrap.ps1" -OutFile "$env:TEMP\sentinel-bootstrap.ps1"
powershell -ExecutionPolicy Bypass -File "$env:TEMP\sentinel-bootstrap.ps1" -Code "PASTE-YOUR-PAIR-CODE"
```

3. Return to the Console and check the device status; a demo-account heartbeat should appear within a minute. You may need to authorize PowerShell Task Scheduler installation on Windows.

The bootstrap downloads into `%LOCALAPPDATA%\SentinelMT5\package`, and Scheduled Tasks run a persistent copy from `%LOCALAPPDATA%\SentinelMT5\app`. The agent token is kept in Windows Credential Manager, not in the web browser. Logs are at `%LOCALAPPDATA%\SentinelMT5\agent.log`.

## Optional: supervise/restart an existing DEMO-only Python trading bot

Do this only if the bot is not already being launched by another service, otherwise it could open duplicate positions. The bot MUST itself enforce `TRADING_MODE=demo` and `SENTINEL_DEMO_ONLY=1`.

```powershell
cd "$env:LOCALAPPDATA\SentinelMT5\package"
py agent.py attach-bot --script "C:\YourBot\main.py"
Stop-ScheduledTask -TaskName "Sentinel-MT5-Agent"
Start-ScheduledTask -TaskName "Sentinel-MT5-Agent"
```

This configures an optional **local-only** process supervisor with exponential backoff on crashes. The website cannot inject shell commands. If the MT5 account switches to a non-demo mode, the supervised process is stopped.

## Reliability

- Auto-start at Windows user logon through Task Scheduler, with restart on failure.
- Independent watchdog task checks the agent every 5 minutes; if the loop heartbeat is stale for over 3 minutes, it verifies the agent process identity before attempting a process-tree restart.
- Retries reconnecting to the terminal and broker on failure.
- Heartbeat every 20 seconds, status marked offline after 90 seconds of missed heartbeats.
- No guaranteed 100% uptime: a powered-off PC, Windows signed-out session, ISP outage, broker outage, account expiry or a major system crash may interrupt execution.
- To minimize downtime, use a paid **always-on Windows VPS** with stable internet and an active MT5 desktop session, plus broker-side protective stop orders.

## Scope of this integration

The dashboard can confirm **Windows Agent + locally verified MT5 Demo connection** and display account balance/equity, open-position count and agent heartbeat. It **does not start an existing unknown Grok bot automatically** or install that bot. To supervise the trading engine, attach its entrypoint locally as shown above.

The previous stand-alone console's trade/strategy/backtest pages remain separate. They do not become broker-executable through pairing alone.

## Security

One-time pairing code is random (20 chars), hashed in DB, single-use and expires after 15 min. Agent token is a random 256-bit secret stored hashed server-side and in Windows Credential Manager. Revoke a device from the MT5 page to invalidate its token. Device status is always untrusted telemetry until verified at the Windows endpoint and should not be regarded as proof of a successful trade.
