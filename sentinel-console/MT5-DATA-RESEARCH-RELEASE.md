# Sentinel MT5 Research Ingestion — Release 2026-11-18

## What this release actually does

**Deployment:** `sentinel-console-isolated-v1` branch, Vercel private console, Neon Functions `sentinelautonomy` triggered every 15 minutes. This release is entirely **DEMO + READ ONLY**; it contains no broker order-creation, modification or closing API calls.

- Read the **actual** TickerAll MT5 Demo account catalog; discover broker-native XAUUSD/GOLD, EURUSD, BTCUSD, NAS100/US100/USTEC names.
- Schedule **one historical market/timeframe import per 15-minute cycle**. The chosen market rotates by the oldest last attempt, not just successful imports; an unreachable market cannot starve the others.
- Record attempts, timeouts, returned coverage, truncated status, observed spread availability and actual closed OHLC bars in Neon; deduplicate by broker account + symbol + timeframe + bar open time.
- Only use fully **closed** candles (TickerAll documents timestamps in Unix *seconds*). Exclude in-progress and future-dated bars.
- For slow XAUUSD and NAS100 requests use shorter historical windows; if the same job times out, use an even smaller retry window rather than hammering the full range. A shorter window may be insufficient for strategy promotion, but data remain genuine.
- Historical price bars with **no observed broker spread** are kept as valid price research, but never treated as proven net-after-cost evidence.
- When enough complete broker OHLC is available without historical spread, generate separate **unverified-cost hypotheses** using an explicit stress assumption. These have **zero reward points and no execution permission**.
- Only broker history with complete coverage and adequate observed spread may advance to the separately validated strategy candidate process. Even those are research candidates; live or demo order execution is not wired to this worker.
- Separate public Binance BTCUSDT research and Crossref bibliography remain enabled and fully labeled. Their results never become broker-verified evidence.
- Intelligence dashboard shows real broker-bar totals, observed-spread coverage, per-market status, research hypothesis counts, worker heartbeat and genuine import errors.

## Evidence at task start

On 2026-11-18 around 11:00 UTC the **previous** worker imported 6,220 EURUSD candles: 4,082 M15 and 2,138 H1; all had missing spread despite `coverage=complete`. It also reported historical fetch timeouts for XAUUSD and USTECH100M. The new rotating worker was designed to fix the timeout starvation and expose those limitations.

## Research promotion gates

- Input candles must be from the customer's verified MT5 Demo broker, timestamp-ordered, fully closed, and the provider must report `coverage=complete` with no truncation.
- At least 900 bars; no rejected or duplicate candles; no more than 25% missing historical spread to proceed to the strict strategy research screen.
- Research candidate generation has chronological validation and held-out windows, twice-cost stress, 16 fixed and bounded parameter variations, daily-block bootstrap and a multiple-testing correction.
- Rewards increase **research priority only**. They must not change trade risk, lot size or account equity.
- Data without observed spread are explored as hypotheses using a 5 bps assumed spread and explicitly marked `UNVERIFIED_BROKER_COST_HYPOTHESIS`, never as broker-validated signals.

## Verified status versus not yet ready

Running: Neon schedule, read-only TickerAll broker polling whenever the demo session is hot, public-crypto hypothesis research, market-quality ledger and dashboard. Real MT5 EURUSD candles arrived and are stored.

Not yet ready: reliable deep XAUUSD / NAS100 history on this particular MetaQuotes Demo server; historical per-candle bid/ask spread, verified broker trading costs, an active forward-demo strategy, automated order submissions, broker-side trade reconciliation, guarantees of unattended TickerAll Free uptime or any profitable strategy.

**Free TickerAll sessions can cool.** This worker intentionally never stores the broker's MT5 password and cannot secretly rewarm after expiration. If the user later elects an always-hot paid plan, that requires separate explicit subscription authorization.

## Operational SQL (read only)

```sql
SELECT symbol,timeframe,COUNT(*)::int AS bars,COUNT(spread)::int AS with_spread
FROM sentinel_brain_candles GROUP BY 1,2 ORDER BY 1,2;

SELECT symbol,timeframe,status,attempted_at,provider_rows,stored_rows,
       coverage,missing_spread_ratio,error_code
FROM sentinel_autonomy_import_attempts ORDER BY attempted_at DESC;

SELECT symbol,timeframe,candle_count,missing_spread_ratio,
       jsonb_array_length(analysis->'hypotheses') AS research_ideas
FROM sentinel_autonomy_broker_hypotheses;

SELECT started_at,status,totals,notes,markets_checked
FROM sentinel_autonomy_cycles ORDER BY started_at DESC LIMIT 5;
```

## Tests

GitHub Actions: `.github/workflows/sentinel-console-check.yml` includes TickerAll documented Unix-second candle conversion, closed-candle guards, source-quality evidence restrictions, native symbols, weekend isolation, bounded retry rotation, encrypted-token integration mocks and order-endpoint isolation. Neon function and Vercel are deployed separately; a green GitHub test does not itself prove provider connectivity.
