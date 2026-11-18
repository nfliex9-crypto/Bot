# Sentinel Independent Trader — DEMO execution engine (not Grok)

- Standalone Python service for Windows MetaTrader5 terminal, stored inside the Sentinel project. It never starts or modifies Grok's existing bot.
- **The archived Grok FusionMarkets Demo login `563722` is a hard-denied account.** Use a *new and separate* MT5 DEMO login (and preferably separate terminal/VPS instance). The server and login are pinned; if account changes it halts.
- Default `research` mode computes closed-bar signals only. `demo_execution` requires changing a local JSON config AND setting `SENTINEL_ENABLE_DEMO_TRADING=YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY` on the machine. No web button can activate execution.
- Two simple baseline families: `trend_pullback` and `donchian_breakout`, long/short, M15 execution filter with H1 alignment. Not yet qualified as profitable by historical or forward tests.
- Native broker `order_calc_profit` determines lot size, default risk 0.25% of equity per trade (hard maximum 0.5%), max daily equity drawdown 1.5%, max two positions, 0.2 lots max. No manual pip value assumptions.
- Bracket SL/TP submitted in the order itself, no naked market entries. Uses broker `order_check`, stop-level and filling-mode validation. Stale quotes, excessive spread, unknown contract values, positions from another magic number or existing pending orders block new entries.
- Durable local SQLite idempotency ledger: unknown/retry-prone MT5 submission outcomes **freeze** the symbol until broker reconciliation proves which trade was placed. Submission ACK is **not** treated as a confirmed final fill. No retry after timeout.
- Polls every 20 sec by default, but checks *closed* M15/H1 candles. One signal per account+bar+strategy+direction. No source names or risk grades are equated with guaranteed profit.
- `state/status.json` is a read-only heartbeat/strategy status. Optional paired Windows agent can forward it to the Sentinel owner dashboard using the bridge; the cloud has no order endpoint.

## Local setup (do not run until ready to test on separate DEMO)

1. On another Windows MT5 terminal, log in to the separate demo and verify it has no unrelated positions or orders.
2. Copy `config.example.json` to `config.json` locally and set `allowed_login` and exact `allowed_server` to that new DEMO. The example intentionally cannot start.
3. Install MetaTrader5 Python package in a dedicated virtual environment on that Windows machine. The Python process requires a running MT5 terminal.
4. Read-only research: `python -m sentinel_trader.run --config sentinel_trader/config.json --once` from the parent package directory.
5. **Only after review, account isolation, tests and approval**, set `mode` to `demo_execution`, and set the local activation environment variable. Never reuse the Grok account or its running MT5 session.
6. Monitor `state/status.json` and the SQLite ledger. Any unresolved intent requires manual broker-level reconciliation rather than blind retry.

## Dashboard / deployment boundary

- `sentinel-bridge/api/trader.js` is for authenticated **read-only status uploads** from a paired DEMO agent only; there is no trading action.
- `sentinel-console/api/trader.js` is an SSO-protected status reader; the console tab does not start or stop bots.
- Apply `schema.sql` on Neon before deploying both Vercel projects; no schema changes were applied during development.
- Deployment remains intentionally disabled until the full system review is finished, per user instructions.
- Actual MT5 broker operation and end-to-end console telemetry are **not** verified by offline mock tests. Results of research signals do not imply trade profitability.
