# Sentinel Adaptive Intelligence V2 — research-first development

**State:** DEVELOPMENT ONLY. No Vercel or Neon deployment of this branch. Existing FusionMarkets-Demo entry authorization has been disabled in Neon independently of this commit. The quarter-hour research trigger and five-minute observation trigger remain enabled.

## V2 decision pipeline

1. **Causal closed-bar ingestion.** Accept M15 and H1 broker OHLC only after full close; reject future, malformed, stale or discontinuous bars. No artificial Delta derived from OHLC or retail tick volume.
2. **Regime state.** Calculate H1 EMA20/EMA50 differential normalized by ATR14; M15 7-vs-42 ATR volatility ratio; 16-bar breakout and normalized candle body / close position. Tag TRENDING, RANGING, VOLATILE or CONTRACTING.
3. **Source provenance.** Price-action source hypotheses must match the owner's exact PDF and page reference. Independent composites have distinct research-only attribution. Source identity is NOT validation of profitability.
4. **Opportunity ranking.** Score trend agreement, price-body conviction, location and local structure. **Score is heuristic quality, never claimed to be win probability**, and never authorizes broker actions.
5. **Separate Order Flow lane.** Executed-trade aggressor Delta is admitted only for exactly the same venue, instrument and candle timestamp. Binance Spot BTCUSDT is NOT Fusion MT5 BTCUSD Delta, and MT5 OHLC cannot supply true Footprint. Mismatches must remain unverified.
6. **Forward learning.** Use complete broker-verified DEMO fills only where strategy attribution happened before entry, entry-time risk amount is known, and chronological data are available. Split earliest 65% training and later 35% untouched OOS. Report gross-R expectancy, win rate, profit factor and sample days. Never auto-promote a family on sample performance alone.
7. **Explainable observation sidecar.** The development runner attaches V2 score, regime, source and data quality to candidate observations, without using these new numbers for orders, risk changes or route selection.

## Current implementation

- `brain/intelligence-v2.js`: pure quality and learning layer, with no external calls, credentials or order interfaces.
- `tests/intelligence-v2.test.cjs`: provenance, causal-data, venue-mismatch, forward-data and no-order regression tests.
- `worker/cloud-trader/runner.js`: development-only read-only integration using the currently supported PDF signal families.
- `.github/workflows/sentinel-v2-ci.yml`: GitHub-only CI, **not Vercel**.

## Inputs V2 still needs before meaningful production learning

- Historic and ongoing broker fills with **pre-trade family label, open time, realized gross profit, stop risk at entry, broker verification, ticket and account**. The existing `sentinel_cloud_trader_fills` table alone lacks the full pre-entry metadata required here; do not fabricate it.
- Verified, instrument-consistent executed-trade feed to make actual Order Flow signals. The uploaded Orderflows course explains setups but is not a market-data API.
- Further historical holdout and forward demonstration evidence, across gold, forex, crypto and indices separately. No profitability guarantee, automatic self-promotion or account-real execution.
- A separately authorized release review and regression validation before any deployment or re-enabling DEMO order entry.

## Research policy

- All backtest and research metrics are **gross, without modeled spread, commissions or slippage deductions**, per user choice.
- Actual broker quote, position, margin and contract correctness must still be verified when the demo order execution path is eventually reviewed; gross backtest outcomes are not actual broker net earnings.
- No unconditional risk escalation, unrestricted leverage, training on future bars, or implicit conversion of educational material into broker permissions.
- **This branch has no live effects** until the owner explicitly requests release. The existing Neon authorizations remain disabled; monitoring can continue normally.

## Next engineering steps

1. Add a true broker fill provenance schema with immutable pre-entry strategy/risk capture.
2. Run longer instrument-matched gross OOS research of the V2 ranked candidates and compare with legacy source signals.
3. Implement a paper-only trade management advisor with recorded evidence.
4. Perform complete offline regression and source-to-rule audit; deploy **once** only after explicit user instruction.
