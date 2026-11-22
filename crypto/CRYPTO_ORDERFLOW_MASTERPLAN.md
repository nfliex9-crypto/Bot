# Sentinel Crypto Intelligence — Order Book / Order Flow Master Plan v1

Date: 2026-11-22. Status: DESIGN / SOURCE-ONLY. Owner intent: a separate crypto-specialized Sentinel that does NOT interrupt, pause, redeploy or modify the existing MT5 bot.

## 0. Immutable separation

- Source: development branch `sentinel-adaptive-intelligence-v2` in `nfliex9-crypto/Bot`.
- New isolated branch: `sentinel-crypto-orderflow-v1`; do not push to `main`, Vercel, Neon, Railway, or any running worker.
- Crypto service and MT5 service MUST use separate credentials, authorization controls, order IDs, strategy registry, storage namespace, execution flags, exchange identity, audit logs and monitoring.
- Baseline mode: `RESEARCH`; then `MARKET_DATA_PAPER` only after full tests. Real orders require separately verified user authorization and a region-permitted venue/product.
- No requirement to change MT5 strategy, cloud cron, or existing account authorization. Read-only observation is allowed. Never equate an enabled DB flag with verified order execution.

## 1. Priority order and acceptance gates

### P0 — Correctness before strategies

1. Audit current Python Binance connector: paper mode currently substitutes *fabricated* ticks (50000/50001) and seeded OHLC bars. Remove this behavior from all purported live-data paper paths. Explicit `SYNTHETIC_FIXTURE` mode for tests only.
2. Resolve order lifecycle defects: no false success in `modify_order`, do not choose an arbitrary open position when closing by ticket, correctly reconcile fills, exchange-specific quantity/price increments, conditional orders and risk checks. Do not call a market order placed if its position protection failed; reconcile or cancel safely.
3. Validate source venue, pair, market kind (spot vs perpetual), contract, tick size, volume units, feed age and data permissions. No claims that Binance Spot BTCUSDT equals MT5 BTCUSD or Bybit perpetual.
4. Default FAIL CLOSED for stale/inconsistent/ambiguous book/trade streams, gaps, duplicate events, unauthorized account/product or missing order protection.

**Gate:** reproducible negative and fault-injection tests, zero fake signals marked live, zero unauthorized orders.

### P1 — Real event data acquisition and replayable storage

- Start with BTCUSDT, ETHUSDT, SOLUSDT research. One venue/instrument/market-type at a time; do not merge different venues without explicit per-venue attribution.
- Ingest REST snapshot + WebSocket depth delta; recover ordered local L2 book using exchange-required update IDs. On disconnect or sequence mismatch, freeze signals and rebuild snapshot. Maintain best bid/ask and depth ladder.
- Ingest *executed* trade tape with event time, receive time, exchange trade ID, maker/taker-aggressor side, price, quantity and venue, not inferred from candles.
- Optional funding, open interest, and published liquidation event streams only when actual venue semantics and permissions are verified.
- Persist immutable compressed event segments, data quality and SHA-256 fingerprints. Keep event-time vs receive-time latency and replay clock separate.

**Gate:** stream gap recovery tests, UTC clock normalization, monotonic sequence, deterministic replay, backpressure, rate-limit, duplicate and disconnect tests; reproduce reference exchange snapshots and trade volumes.

### P2 — Microstructure Intelligence

Derive documented, venue-scoped features from raw events:

- L2: top-N queue imbalance (size weighted and distance weighted), microprice, bid/ask changes, persistence/dwell time, cancellation-to-placement ratio, replenishment, quote fade and sweep-through.
- Taker tape: signed volume `delta = buy_aggressor_volume - sell_aggressor_volume`, intrabar extrema, session CVD, CVD/volume, trades per price bin, footprint imbalances, rolling volume bursts, large prints relative to asset/session distribution.
- Price + tape: absorption research candidate only when aggressive volume, price response and *observable opposing liquidity replenishment* agree; exhaustion and delta divergence with confirmed execution tape. Never label a hidden iceberg or manipulation as a fact on L2 observations alone.
- Distinguish displayed resting liquidity from executed trades. A large wall can cancel before price reaches it; no profitable-entry inference from wall size alone.
- Across venues, use synchronized, separately tagged features to corroborate; no invented consolidated global order book.

**Gate:** synthetic known-answer vectors + real recorded event replay; each feature with formula, provenance, latency, limitations and at least one rejection example.

### P3 — Formal rules and training curriculum

Reuse the already source-traced 5-video Orderflows Delta curriculum with exact provenance, but keep the unverified audio and four unspecified course setups BLOCKED. Existing tested Delta Surge and Divergence OOS were negative in the prior limited BTC spot replay: do not promote them as profitable.

Candidate families to research, each long and short where the actual instrument permits:
A. Sweep / failed breakout + delta divergence + measured absorption + price structure confirmation.
B. Breakout continuation + multi-level resting liquidity depletion + sustained positive/negative taker pressure + HTF context.
C. Range-reversal / auction rejection + aggressive trades unable to move price + confirmed turn and invalidation.
D. Trend pullback with liquidity replenishment, bid/ask alignment and retracement confirmation.
E. Liquidity vacuum / rapid book thinning as a *volatility warning* and exit signal, NOT an automatic direction forecast.

Each spec MUST state: market regime, venue, market type, timeframes, signal definition, data source, timestamp cutoff, invalidation, position sizing source, risk and exit conditions, version, train/test cuts, and number of tried parameters.

**Gate:** exact reference examples reproduced, no hindsight labels, no promotional classification from synthetic data.

### P4 — Bookmap & DeepCharts integration

- Bookmap: optional desktop add-on/bridge through documented Java/Python add-on APIs (depth + trades where data entitlement and API allow). Its heatmap is a view of the order book and our system may recreate key measurements from native venue feed. No reliance on screenshots for the live trading engine.
- DeepCharts / DeepDOM: use verified visual/educational chart features to compare footprints, volume profile and trades. A suitable publicly documented external machine-data API is NOT confirmed; do not invent one or assume automated scraping is licensed.
- Optional training dataset: user-provided authorized videos/images can be annotated by timestamp; overlay bot-generated values and human labels to measure agreement, NOT replace missing exchange tick events.

**Gate:** 1:1 symbol/venue/time alignment, derived values match externally displayed examples within stated granularity, source/license audit.

### P5 — Backtest and OOS validation

- Event-driven replay of historical L2 + actual trade tape; execute signals only on data that was already available at that event time. Use closed-bar features when rules require close.
- Validate on multiple chronological purged walk-forward windows, an untouched final holdout, varied bull/bear/range/high-volatility regimes, independent crypto assets and (where possible) a second venue.
- Explicit outcomes: trades, time-in-market, win rate, expectancy in R, drawdown, adverse excursion, symbol/regime breakdown, edge decay, confidence intervals, and number of screened hypotheses.
- Separate gross-price research from execution accounting. For paper fill realism include actual bid/ask and order book queue/partial fill rules. When explicit fee assumptions are disabled for the gross research layer, label it `GROSS_ONLY_NOT_NET_PROFIT` and do NOT claim live profitability.
- Promote successful candidates to *paper research only*; reject weak ones and generate a bounded set of new hypotheses. Keep a fixed, auditable strategy genealogy.

**Gate:** repeated positive out-of-sample evidence across distinct conditions, stable sensitivity under small parameter changes, complete proven data lineage. No guarantee of returns.

### P6 — Continuous paper trading and live dashboard

- Paper trades only against genuine market data (never synthesized candle prices) with venue-compatible order sizing, realistic bid/ask fills and replayable order lifecycle.
- Dashboard: venue and symbol source, stream health, true heatmap, footprint/CVD, L2 imbalance and liquidity persistence, active hypothesis and rejection reason, confidence calibration, trades, outcomes, strategy genealogy and stale-data alarms.
- Separate service heartbeat, restart recovery, sequence resync, paper position reconciliation, incident log, human pause control.
- 24/7 research scheduler may read and test even when no order is valid; trading can legitimately remain idle.

**Gate:** independent paper validation, no false live badges, stable uptime tests, restart idempotency, no more than one trade emitted from duplicate signal events.

### P7 — Conditional live activation (NOT authorized now)

- Verify current Belgian/EU exchange and product eligibility; an exchange offering Spot does not imply futures/perpetual access.
- Explicit written enablement for a specific independent crypto account, API scopes excluding withdrawals, venue, instruments, mode and approved order sizing.
- Enforce exchange filters, available margin, max loss from stop, order protection and emergency cancel/flatten/disable. Realized P&L must be reconciled from venue.
- No deployment, funded trade, or shared MT5 authorization as part of this spec.

## 2. Component interfaces

Normalized event envelope:
`{venue, instrument, market_type, event_type, event_id, exchange_seq, event_ts_ms, recv_ts_ms, price?, quantity?, aggressor_side?, bids?, asks?, snapshot_id?, source_quality}`.

Core services:
`venue-adapter -> sequence-validator -> immutable-event-store -> L2-book + trade-tape -> feature-engine -> regime/structure analyzer -> candidate-ranker -> execution-gate -> paper-executor -> audit/dashboard`.

The feature engine MUST not use the user-visible platform's chart pixels as a real-time executed trade feed.

## 3. Current verified source inventory at planning time

- `app/brokers/binance_broker.py` has an incomplete venue adapter and synthetic paper data fallback.
- `sentinel-console/brain/orderbook.js` provides **research-only** snapshot diagnostics and persistence checks, not a live rebuilt L2 feed.
- `sentinel-console/brain/orderflows-delta-curriculum.js` encodes course metadata and 3 verified visual rule families; 4 setup names are underspecified.
- `sentinel-console/worker/orderflow/delta-engine.js` is intended for verified executed trade tapes; must verify against real venue data.
- `sentinel-console/brain/backtests/ORDERFLOWS_DELTA_BTCUSDT_2026-11-21.md` documents negative OOS Surge/Divergence observations on limited Binance spot data. This blocks profitability claims.
- The present V2 development is NOT yet a verified deployed 24/7 crypto orderflow trading system.

## 4. Primary official references (to recheck before implementation)

- Binance Spot WebSocket and local book reconstruction: https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md
- Bybit V5 Orderbook/Trades: https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook and https://bybit-exchange.github.io/docs/v5/websocket/public/trade
- Bookmap API: https://bookmap.com/knowledgebase/docs/API
- Bookmap Python add-on: https://github.com/BookmapAPI/python-api
- DeepCharts overview: https://www.deepcharts.com/helpcenter/deepchart-web/article/deepchart-web-overview
- FSMA crypto provider information: https://www.fsma.be/en/list/authorised-belgian-crypto-asset-service-providers

## 5. Delivery definition

This file records the blueprint only. Creating it does NOT indicate a collector is running, tests have passed, strategies are profitable, broker access is available, or any orders have been made. The next engineering action is P0 connector audit and real L2/tape collector with unit tests, exclusively in the isolated crypto development branch.
