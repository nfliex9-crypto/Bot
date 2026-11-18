# Sentinel MT5 Quant Hardening — 2026-11-18

## Scope and verified baseline

Target is \`nfliex9-crypto/Bot\` branch \`sentinel-console-isolated-v1\`, NOT the old production \`Bot\` branch or an unidentified live bot inside Grok. This branch is DEMO research and monitoring only.

Latest checked Neon snapshot (UTC ~14:10, 2026-11-18): 6,230 TickerAll MT5-demo EURUSD bars: 4,091 M15 and 2,139 H1. Historical spread coverage 0%. There were 23 automation cycles (4 completed, 11 partial, 8 waiting), 4 EURUSD broker-hypothesis rows, 0 promoted candidates and 0 tagged/recorded strategy trades. Gold (XAUUSD) and USTECH100M historical imports had timed out. TickerAll quote observations existed separately (4 samples each on EURUSD, gold and USTECH100M), but must not be backfilled into historical candle spreads.

## Changes in this development branch

1. **Slow native-symbol history:** Gold and NAS history jobs start with 24-hour probe; after *successful* snapshots the window progresses 24 -> 72 -> 168 -> configured hours based on received bars. After a timeout the next retry is compact and remains fairly interleaved with other markets. This can reduce timeout work but cannot guarantee a broker has deep history. Quality gates remain unchanged.
2. **Reproducible challengers:** When real broker OHLC exists without historical spread, the hypothesis lab screens 16 baseline ideas plus up to 8 bounded new parameter variants per immutable dataset fingerprint; repeated identical data produce identical ideas. Each screened variant counts in the multiple-testing correction. No reward, execution permission, or real profit is inferred from assumed costs.
3. **Native Windows MT5 DEMO history:** \`export_history.py\` reads CLOSED M15 or H1 bars and converts the MT5 \`spread\` column from points to absolute price using \`symbol_info.point\`. It rejects real accounts, absent terminal connectivity, invalid symbols and timestamps. It never sends orders and never accesses a broker password.
4. **Opt-in local-to-bridge transfer:** \`upload_history.py\` uses the EXISTING paired device secret in Windows Credential Manager. \`sentinel-bridge/api/mt5.js?action=candles\` accepts no more than 500 validated closed bars and 128 KiB, and only when the paired agent has a fresh DEMO heartbeat and matching account last four digits. Data are segregated under \`native-demo-<agent-id>\`, marked \`local_unverified\` and \`truncated=true\`. This is not a broker certificate and cannot promote a strategy. No trade APIs were added.
5. **Order Book module:** \`brain/orderbook.js\` can validate fresh Level-2 snapshots, calculate top-N depth imbalance, spread, microprice and temporal persistence, with fail-closed handling of stale, locked/crossed, malformed and mixed-source books. It never produces a buy/sell instruction and it is NOT connected to a live depth feed yet.
6. **Source distinction:** Dashboard API groups bars by \`account_id\` and exposes a source category rather than merging broker API history with local unverified uploads.

### Demo-only native upload procedure (once branch is deployed)

On the Windows machine where the Sentinel agent is paired and MT5 DEMO is running, from the agent folder:

\`\`\`powershell
py upload_history.py --symbol XAUUSD --timeframe M15 --bars 500
py upload_history.py --symbol XAUUSD --timeframe H1 --bars 500
py upload_history.py --symbol USTECH100M --timeframe M15 --bars 500
\`\`\`

The exact symbol must be present in the local MT5 Market Watch. User must install/retrieve the updated script on their Windows computer; the current server cannot reach their laptop's MT5 process. A \`202 accepted\` confirms storage only, not verified historical P/L. For an offline file (no cloud upload):

\`\`\`powershell
py export_history.py --symbol XAUUSD --timeframe M15 --bars 3000 --out "$env:USERPROFILE\Desktop\XAUUSD-M15.json"
\`\`\`

## Assessment / prioritized work

| Priority | Gap | Correct next milestone |
|---|---|---|
| P0 | Real Grok trading bot source identity remains unknown; Sentinel is not proven connected to its order engine | Obtain its repository/export and inspect actual entry/exit, broker login mode, position ownership, test coverage, and live logs |
| P0 | No validated positive strategies or tagged demo forward results | Keep execution off; research champion/challenger and collect immutable forward fills before considering paper orders |
| P0 | TickerAll first/slow symbols and spread gaps | Measure compact retry success; use verified local MT5 terminal rates + symbol specs, but distinguish locally exported quotes from execution truth |
| P0 | Position reconciliation, broker-native lot sizing, persistent risk gates are not in this new worker | Introduce a separate DEMO-only OMS with idempotency, restart reconciliation, native tick/contract specs, daily shutdown, protective broker SL |
| P1 | L2 / market-by-order collector absent | For BTC use a real exchange's ordered depth updates + snapshots and gap-resync; for GC gold futures subscribe to properly licensed depth/trade feeds; MT5 CFD DOM is broker-specific and may be unavailable or unrepresentative |
| P1 | Current OHLC strategy family too narrow | Research opening-range, auction/VWAP, pullback continuation, range-failure, momentum/reversion conditioned on volatility and session — only if their required data are genuine |
| P1 | Selection research is not robust production learning | Purged time-series split, realistic execution simulator, trial registry and multiple-testing adjustment, parameter-stability surfaces, cost stress, regime drift, true forward demo |
| P2 | Operational resilience and false status UI | Dedicated 24/7 Windows/worker host, freshness alerts, health probes, latency monitoring, provider fallback, explicit \`no_data\` vs \`no_trade\` UI |

## Order-book model — what "understanding the market" requires

- **Venue:** Order books are not universal. Centralized COMEX GC futures depth is not the spot gold / XAUUSD CFD book; BTCUSDT exchange depth is not automatically a BTCUSD broker CFD fill quote. Retail FX has no single complete central order book.
- **Correct reconstruction:** Exchange WebSocket *incremental* updates must match REST snapshot update IDs; detect sequence gaps, discard stale snapshots and rebuild. Include exchange timestamp, ingest timestamp, sequence, bids/asks, trades and instrument contract mapping.
- **Research features:** depth imbalance and microprice, order-flow imbalance (proper event changes), cancellations/replenishment, sweep-driven absorption confirmed against trade prints, liquidity vacuum, temporal persistence and response after a level is touched.
- **Anti-spoofing/evidence:** Large resting walls can disappear. Require persistence and *executed trades* to distinguish passive resting orders from aggressors. Use leave-one-day-out and session-conditioned future-return labels, accounting for latency and spread. Test both directional predictive value and realistic fill probability.
- **Execution boundary:** L2 feature scores may filter a fully validated strategy; do not turn any single depth ratio into automatic buy/sell orders.

Official source material: https://www.mql5.com/en/docs/python_metatrader5/mt5marketbookget_py ; https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md ; https://www.cmegroup.com/market-data/browse-data/catalog/futures-and-options-data.html ; https://tickerall.com/docs

## Verification boundary

GitHub Actions unit tests check source contracts and mocks; they cannot confirm a user's connected Windows MT5 terminal, broker data availability, current deployed code, correct real-world L2 feed subscription or trading profitability. No live or demo orders should be placed automatically by this branch. Deploy explicitly only after CI and protection checks, with the Vercel bridge and console deployed from their corresponding isolated directories. Live real-account trading is out of scope.
