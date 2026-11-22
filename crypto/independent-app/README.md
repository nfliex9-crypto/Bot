# Sentinel Crypto Futures — INDEPENDENT PROJECT

This folder is the **packaging source** for a completely separate GitHub project called `sentinel-crypto-futures`. Its release ZIP is constructed by the `crypto-standalone-package.yml` workflow, which copies **only** the WEEX Futures `src/` and the independent `app/` + `dashboard/`. It contains NO MT5 code, account permissions, broker connection or shared database.

**User-facing dashboard:** dark, responsive UI at localhost:8765; 3 real WEEX USDT perpetual markets; demo account explicitly DISCONNECTED; order execution explicitly OFF. A stale or absent feed shows "Unavailable" instead of invented quotes.

## Independent local quickstart

From the root of the **extracted standalone package**, on a computer with Python 3.13:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
python -m pip install -r src/requirements.txt

# Terminal 1: **public** WEEX Futures feed to local data/ only
python app/collector.py --symbols BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT
# Terminal 2: local READ ONLY dashboard
python app/server.py --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 on the **same computer**. No demo credentials required for public market data. Press Refresh to see only fresh actual WEEX market observations.

### Demo credentials

**Never paste API keys, API secrets or passphrases in ChatGPT, a screenshot, a commit or a tracked `.env` file.**

Create a **private separate GitHub repository**, then use `Settings → Secrets and variables → Actions → New repository secret` (desktop mode if mobile Settings is hidden). Use three distinct names:

```text
WEEX_SIM_API_KEY
WEEX_SIM_API_SECRET
WEEX_SIM_API_PASSPHRASE
```

Use a **Read-only** WEEX key first. A regular WEEX-production key does not prove simulation authorization. The **standalone** workflow uses **Repository Actions secrets**, not the GitHub Environments page that was unavailable on mobile. For local checking, supply the variables in a secure local shell to `python src/weex_demo_account.py`; the script reads only the official WEEX Futures SIM balance endpoint.

The private endpoint guard pins requests to `https://api-sim.weex.com`; **NO FUTURES DEMO ORDER EXECUTION is enabled**. Public Futures market-data monitoring is independent of account connection.

### Status honesty

- Real Futures order-book best prices and last real executed trade are read through official CCXT Pro WEEX adapter (no Spot data).
- The service writes only source-labelled **ephemeral** market summaries. Raw WEEX Futures Parquet capture is a separate `python src/weex_futures_parquet.py --out-dir ...` process. A local dashboard is not proof of 24/7 hosted availability.
- Refusal to show market data if any stream is stale after 15s.
- No shared secrets with MT5, no MT5 imports/DB/HTTP/API routes/positions.
- No private trading UI or order execution route exists.
- The existing detailed WEEX tests and data research scripts are retained inside `src/`; only trusted public-data claims count.

### Shared *ideas*, never shared privileged resources

Both projects may use the **same engineering patterns**: contract tests, health checks, signal validation, replay, audit logs and market-data provenance. This is code-pattern reuse only. No MT5 production code, tokens, trading orders, runtime process or database are imported.

### Deployment state

No live service has been deployed. The linked Railway trial account rejected creating a new project due to an expired trial; this does not affect independent GitHub packaging. Do not enable public access to the dashboard without designing authentication.
