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

## Faster broker-connected monitoring (optional)
Requires only existing TickerAll account connection, database, and stored encryption key; no separate MT5 Windows terminal or new API account. Run `npm run cloud:loop` to poll roughly every 60 seconds as a private worker (not automatically deployed). `npm run cloud:once` performs a one-time shadow evaluation. Existing 15-minute research worker also invokes cloud monitoring. Neon lease serializes competing cycles. Broker hot state can still expire, so 24/7 availability is NOT proven and no paid always-hot setting was changed.

## Closed broker deals and research provenance
`sentinel_cloud_trader_fills` stores only complete matching broker-history closed trades, by previously recorded Sentinel order ticket, in deposit currency with broker commission and swap. Order acknowledgment is NOT realized P&L. `sentinel_autonomy_candidates` supplies research context, but OHLC paper hypotheses remain UNVERIFIED and NEVER auto-approve an execution strategy. Demo trial order gates remain OFF unless explicitly configured in a private worker after separate review.

## Fusion DEMO cloud trial — 19 November 2026
The broker must be linked through TickerAll, and its session must be hot, MT5,
DEMO and trade-capable. Neon independently runs the research trigger every
15 minutes and the cloud trader monitor every 5 minutes. The research engine
prefers the single linked Fusion demo just like the cloud trader.

The additive `sentinel_cloud_trader_authorizations` table is an alternative
private-operator authorization mechanism. An entry must match the exact
TickerAll account ID, exact Fusion broker server, masked last four digits,
a future expiry, enabled=true and risk_pct in (0, 0.25]. The engine rechecks
all of these and both broker account type and quote/contract specifications
before every demo entry. Disabling or expiring the database row stops new
orders; it does not close existing broker positions.

Trade entries are unvalidated DEMO experiments, NOT strategy performance
claims. A genuine signal is required from a closed M15 candle with H1 trend
confirmation; never inject a dummy signal merely to force the first deal.
A source missing broker-confirmed account-currency tick value cannot be
used for risk sizing. No real-account orders are permitted.

The research factory remains separate: OHLC-only datasets with unverified
historic spreads can create labeled hypotheses but NEVER promote strategies
to live capital. Forward broker fills and fees must be checked independently.
