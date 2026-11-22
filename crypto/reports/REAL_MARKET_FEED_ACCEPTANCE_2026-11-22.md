# Sentinel Crypto — independent external market data acceptance
**UTC date:** 2026-11-22. **Release scope:** GitHub-only research, no cloud deployment, no exchange-account credentials, no orders. **Parent MT5 unchanged.**

## Verified E1: Cryptofeed 3.0.5 / Kraken SPOT / BTC-USD

**GitHub workflow run:** https://github.com/nfliex9-crypto/Bot/actions/runs/45030194329  
**Job:** Real Kraken Spot L2 + trades (read-only), `SUCCESS`.  
**Source:** Cryptofeed 3.0.5 exchange-normalized Kraken callbacks, official upstream public WebSocket and REST instrument lookup.  
**Timestamp of observed witness completion:** 2026-11-22 **13:58:28 UTC**.

Exact JSON metrics printed by the GitHub runner (historical proof of a live observation, NOT current market prices):

```json
{"best_ask":60650.3,"best_bid":60641.7,"executed_trade_callbacks":87,"invalid_events":0,"last_book_age_seconds":0.16,"last_trade_age_seconds":0.74,"market_type":"SPOT_PUBLIC_ONLY","order_book_callbacks":2134,"orders_enabled":false,"source":"cryptofeed_3.0.5","status":"VERIFIED_RECENT_EXTERNAL_EVENTS","symbol":"BTC-USD","synthetic_market_data":false,"venue":"KRAKEN"}
```

Interpretation: A single 45-second independent connection received BOTH recent, non-crossed Kraken public L2 book and executed trade events, each identified by venue, pair and exchange timestamp. No account/execution permission was needed or exercised. This is sufficient to accept **read-only source connectivity** at that one moment; it is NOT a claim of 24/7 reliability or strategy performance.

## Verified E2: official PCAP capture, not a fabricated indicator

GitHub job used the **official** `bmoscon/cryptofeed` release tag `v3.0.5`:
```bash
python examples/record.py KRAKEN BTC-USD --duration 20 --out ./crypto-captures/
```

Real upstream job output (2026-11-22 **13:58:59 UTC**):
```
capture: ./crypto-captures/cryptofeed-20261122-135839.pcap.zst
metadata: ./crypto-captures/cryptofeed-20261122-135839.meta.json
KRAKEN.http.0: received=1 sent=0
KRAKEN.ws.1: received=2511 sent=2
```

**GitHub artifact:** https://github.com/nfliex9-crypto/Bot/actions/runs/45030194329/artifacts/14757153684
- Name `crypto-public-kraken-pcap`
- ZIP length **153,803 bytes** according to GitHub artifact metadata
- ZIP SHA256 `7c5d4bd3484b0aba96415d4f4c46ceec33862b0ec3b621503fdb4666c01593f6`
- Retained 7 days; expires 2026-11-29 13:58:59 UTC. This link is a **temporary** CI artifact, not persistent storage.

**Data-privacy rule:** This is public market data only; do not store broker secrets or private account info in the public GitHub repo.

## Verified E3: contract tests, real upstream installer

- `Source freshness and fail-closed contract` job: **SUCCESS** in run 45030194329, 14 local Python test cases also passed independently.
- Independent `NautilusTrader v2 crypto adapter (READ ONLY)` run: https://github.com/nfliex9-crypto/Bot/actions/runs/45030194279, **SUCCESS** on official pinned `nautilus_trader==2.0.0rc9`. Wheel installed, data-only node constructed successfully. **This job verified build/import, not receipt of real Nautilus L2 or trades.**
- A later source code audit found default `DataTesterConfig.subscribe_book_deltas=False`. We corrected the integration to explicitly subscribe with `subscribe_book_deltas=True` and `book_depth=10`; the next CI job must verify this exact configuration. Do not retroactively claim the first Nautilus build had received book deltas.

## Acceptance / next gates

1. **Accepted:** Public Cryptofeed real Kraken Spot BTC-USD TRADES + L2 source.
2. **Accepted:** Official upstream PCAP capture and 14 Python validation tests.
3. **Conditional:** NautilusTrader native Kraken Spot L2 subscription. Verify follow-up hosted job with explicit deltas, real live messages, health and recovery.
4. **Not yet built:** Historical PCAP replay into a validated Nautilus research catalog; verified trading signals, order-flow alpha, paper fills, 24/7 persistent collector and dashboard.
5. **Blocked:** Any funded crypto account, perpetuals, Bookmap licensed add-on or DeepCharts machine API, until specifically verified and authorized. No real order route exists in this prototype.

## Known limitations

- A top-10 Kraken L2 snapshot cannot reveal hidden orders or all liquidity elsewhere.
- 45s is a connectivity test, not a statistically valid period for trading research.
- Feed freshness in the witness means recency as observed by runner, not a venue-wide availability guarantee.
- Kraken Spot is not Binance Spot, Kraken Futures, MT5 BTCUSD, or a globally consolidated order book.
- NautilusTrader 2.0.0rc9 is a *pre-release*: research and testing only, not a proven safe funded trading implementation.
- No Vercel, Railway, or Neon instance was created or changed; MT5 production remains outside the scope.

## Verified E4: Native NautilusTrader v2.0.0rc9 live Kraken Spot (same day)

**GitHub Actions:** https://github.com/nfliex9-crypto/Bot/actions/runs/45030670151 — `official-venue-adapter-smoke` **SUCCESS** on Linux / Python 3.13.

- Installed exactly `nautilus_trader==2.0.0rc9` upstream research pre-release.
- Verified `KrakenDataClientConfig(product_type=KrakenProductType.SPOT)`.
- Verified `DataTesterConfig.subscribe_book_deltas=True`, `manage_book=True`, `book_depth=10`, `subscribe_trades=True`, before launching.
- Built data-only LiveNode without registering an execution client; `Environment.LIVE` means current public exchange market data, **not a funded trading account**.
- Started native Kraken spot connector and upstream `DataTester` actor for a short timed observation. CI required an **actual emitted `TradeTick {`** in output, and printed the acceptance marker `NATIVE_NAUTILUS_REAL_TRADE_TICKS_OBSERVED`. No executions, demo or otherwise.
- Recorded diagnostic artifact: https://github.com/nfliex9-crypto/Bot/actions/runs/45030670151/artifacts/14757875429 (ZIP 60,191 bytes, digest `sha256:26dfee574070c3564cc5b259491ebee1145aeb815462d4b6f2def47d743b2343`, temporary 7-day retention).

**Limits of this evidence:** CI asserts native L2 subscription and the presence of a live trade tick; it does **not yet** include an independent explicit count/continuity assertion for native reconstructed depth levels over a long run. Cryptofeed's independent E1/E2 tests establish a separate real Kraken order-book source for the same market. Neither observation proves 24/7 uptime, execution, strategy edge, or Bookmap/DeepCharts integration.

### Revised acceptance
- `PASS`: Cryptofeed upstream public trade/L2 connectivity with actual source recorder; test and PCAP artifact.
- `PASS`: NautilusTrader official Kraken Spot live read-only data client, real TradeTick emitted, required L2 subscription configuration verified.
- `PENDING`: native L2 continuity/restart and long-run health tests; persistent storage/replay; event-driven backtest and genuine paper results; no service deployment yet.
