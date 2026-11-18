# Sentinel Cloud MT5 DEMO — development, not deployed
Uses the *existing* Sentinel encrypted TickerAll token stored in Neon and the already registered TickerAll MT5 demo session. No separate Windows MT5 terminal, new broker account, new password or additional API key is required. The Windows/native trader remains optional and separate; Grok is untouched.

## Modes
Default **SHADOW_ONLY**: read-only account, positions, broker symbol catalog, M15/H1 closed candles, quote and account-currency contract specs; record decisions in Neon. No broker write API call is possible without *all* of:
- SENTINEL_CLOUD_MODE=demo_execution
- SENTINEL_CLOUD_ENABLE_DEMO=YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY
- SENTINEL_CLOUD_UNVERIFIED_TRIAL=YES_EXPLICIT_DEMO_TRIAL
- SENTINEL_CLOUD_ACCOUNT_ID=<EXACT_CONNECTED_TICKERALL_MT5_DEMO_ACCOUNT_ID>

All four must be explicitly configured in the private worker environment. These values are NOT configured in the repository; no trading enabled in this release. This mode is an **unvalidated demo experiment**, not verified alpha. No live-account orders. Do not enable without checking the actual broker session, costs and backtest/forward evidence.

## Operation
Run additive migration `sentinel-console/migrations/2026-11-18-cloud-demo-trader.sql` before worker deployment. Existing 15-minute research cron/loop now calls cloud monitor *after* research; Neon lease prevents concurrent cloud cycles. Dashboard trader status uses SSO-protected read-only API; missing local-Windows telemetry table is tolerated.

Symbols are discovered from the broker, prioritizing Gold/XAUUSD, BTCUSD, NAS100/USTECH100M, and EURUSD. Signal rules are research baselines only (EMA pullback, Donchian breakout) and may not be profitable. Execution is idempotent via unique Neon signal hash + TickerAll Idempotency-Key; network ambiguity is NEVER automatically retried and blocks the account pending verified broker position/history. Broker-specific tickValueAccount, tickSize, stops, spreads, and a daily 1% equity lock limit orders. Historical data with incomplete coverage or unknown cost specifications cannot execute.

TickerAll currently does not supply exchange-grade order book for this integration; the MT5 Windows DOM observer remains independent research-only. Trade-profit figures must never be inferred from order receipts. A broker deal reconciliation with verified commissions and slippage is still needed for a fully evaluated 24/7 strategy.

## Tests
`node --test sentinel-console/tests/cloud-trader.test.cjs`
