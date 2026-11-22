# Sentinel Crypto Intelligence — External-first Master Plan v2

> **2026-11-22 PRODUCT PIVOT — SUPERSEDES PRIOR SPOT TARGET.** The user's new goal is **WEEX USDT Perpetual Futures DEMO**, NOT Spot trading. The Kraken Spot historical tests below are archived R&D results and must NEVER be used as WEEX futures training labels, order-book signals, broker prices or fills. No active Spot jobs. The new active path is [crypto/futures-demo/README.md](./futures-demo/README.md) and [GitHub WEEX Futures CI](../.github/workflows/crypto-weex-futures-demo.yml). The CCXT Pro WEEX public FUTURES L2/trade WebSocket has been verified on GitHub with authentic exchange data; WEEX simulation account authentication and demo order placement require a separate demo API credential and are NOT yet active.

**Decision:** 2026-11-22. **Mode:** independent GitHub R&D. **Owner directive:** depend on vetted upstream market-data, order-book, order-flow, backtesting and execution engines. **Do NOT build those products from scratch.**

## Independence from existing MT5

No changes to MT5 broker, account permissions, cloud trader authorizations, strategies, schedules, Railway, Neon or Vercel. This is an isolated GitHub branch `sentinel-crypto-orderflow-v1`. Paper/real crypto orders are OFF. Our account-specific production control requires separate explicit user approval.

## External platform roles (no two competing execution engines)

1. **NautilusTrader** — intended primary engine: Rust order books, venue adapters (Binance / Bybit / Kraken, where supported), normalized trades, order and fill lifecycle, backtest/replay, optional single execution engine. Pin 2.x release candidate only after compatibility smoke tests; current official latest docs describe 2.x, not stable v1.x. See https://nautilustrader.io/docs/latest/getting_started/installation/ and https://nautilustrader.io/docs/latest/integrations/binance/.
2. **Cryptofeed 3.0.5** — read-only multi-exchange trade / depth capture, operational independent witness and upstream PCAP recorder; it is NOT a second order execution engine. Source https://github.com/bmoscon/cryptofeed and official https://github.com/bmoscon/cryptofeed/blob/v3.0.5/examples/record.py.
3. **Bookmap** — use licensed workstation add-ons, heatmap, liquidity history and visuals for independent verification. Only link data back via supported API with proper data rights; not a free generic data reseller. https://bookmap.com/knowledgebase/docs/API
4. **DeepCharts / DeepDOM** — read external vendor Level 2 and review footprint/DOM; outbound API not yet verified. No invented integration or screenshots pretending to be tick tape. https://www.deepcharts.com/helpcenter/deepdom/article/installation-and-first-configuration
5. **Hummingbot** — alternative execution framework if NautilusTrader cannot meet an approved venue; never have both engines place orders on the same account.

## Progressive milestones and acceptance criteria

### P0. Source integrity — READY FOR LIVE CONNECTIVITY TEST
- Version pin Cryptofeed v3.0.5 and use its official implementation; a tiny verifier subscribes only to L2_BOOK and TRADES, rejects missing, invalid or stale data.
- GitHub workflow performs unit checks and a genuine 45-second Kraken Spot BTC-USD market data test. It captures upstream PCAP frames. **A configured workflow is not evidence that a run passed.**
- No synthetic trading dataset can be labeled real. Source names (KRAKEN BTC-USD vs BINANCE BTC-USDT), product types, and timestamps must remain isolated.
- P0 completes only after the hosted workflow reports real callbacks and retains exchange-origin capture. Any exchange access problem is reported, not bypassed.

### P1. Native order book and trade feed (UPSTREAM, not custom)
- Use NautilusTrader's own managed L2 OrderBook updates and Binance/Kraken/Bybit venue adapter(s) for instrument-specific trade event streams.
- Book reconstruction, exchange sequence recovery and market session/event timestamps remain the responsibility of the upstream adapter.
- Install, dependency-lock, replay and continuity-test upstream rather than writing replacement exchange WebSockets.
- Verify exchange-symbol precision, bid < ask, event freshness, disconnects, UTC times, and cross-venue attribution without fabricating any missing information.

### P2. Trusted order-flow calculations / research
- Use upstream trade tape/order book fields to verify Delta, CVD, volume profiles, top-of-book and replenishment hypotheses.
- Import the five-video Orderflows Delta curriculum from Sentinel as **reference only**, with source-level provenance.
- Previous limited BTCUSDT Spot OOS for Surge / Divergence was negative; those research hypotheses are NOT auto-approved.
- Bookmap/DeepDOM must receive the SAME venue/symbol/feed and recorded-time scope for visual comparison.

### P3. Strategy evaluation, not blind self-training
- Use NautilusTrader event-driven historical and live replay, compare the actual timestamped tape/depth events under locked strategy versions.
- Purged forward/OOS, varied bull/bear/range regimes, multiple assets, separate final holdout and no hindsight labels.
- Report gross-only research separately from actual bid/ask, fills, costs and broker accounting. Never claim gross returns are realizable profit.
- Only documented positive repeated OOS evidence can promote *paper candidate* priority, never live orders.

### P4. Paper-trading service with independent dashboard
- Run NautilusTrader paper/replay adapter (venue-appropriate), with separate instance, credentials, database and audit history from MT5.
- Health endpoints show real source, age, venue type, trade tape and L2 gaps, and provenance. NO fake live indicators.
- Persistent 24/7 hosting requires resource, restart, monitoring and data-retention validation.

### P5. Optional real order execution
- Verify Belgian/EU exchange permissions and particular Spot vs perpetual product rights.
- Choose one audited executor; validate market filters, order protection, fill/order/position reconciliation, API scopes without withdrawal and operator shutdown.
- Only after explicit approval of an identified crypto account and chosen venue.

## Delivery ledger

- DONE: isolated GitHub branch; external provider selection; read-only Cryptofeed witness; pinned dependency; 7 deterministic contract tests authored; workflow defined.
- UNVERIFIED: GitHub hosted live WebSocket test pass, actual PCAP artifact, NautilusTrader 2.x runtime compatibility on chosen host.
- NOT DONE: 24/7 live daemon deployment, Binance/Bybit/Kraken account connection, Bookmap addon connection, DeepDOM data export, trading signals, paper fills, demonstrated profitability, real exchange order submissions.

## Setup

See [external-stack/README.md](./external-stack/README.md) for direct upstream PCAP capture and read-only live data verification.

**Trading safety and ownership:** MT5 remains untouched. The new crypto system starts as market-data research only, and passes to paper trading only after genuine live feed validation. No return claims or simulated orders represented as real.
