# Sentinel V2 broker-archived OHLC gross replay — 22 Nov 2026

**Status:** RESEARCH ONLY. No Neon data mutation or order placement; no production release.

## Data origin and sample sizes

The existing Neon `sentinel_brain_candles` history was read **only** for the exact account in `sentinel_cloud_trader_authorizations` with `expected_last4='1964'` (FusionMarkets-Demo). These are **previously archived broker OHLC**, not independently re-verified ticks or true executed-trade Delta. There are **no historical bid/ask executions, order book, actual slippage or commission deductions** in this replay.

| Instrument | M15 | H1 |
|---|---:|---:|
| EURUSD | 4,320 | 2,180 |
| BTCUSD | 5,939 | 3,004 |
| XAUUSD | 1,073 | 111 |
| NAS100 | 1,066 | 109 |

Repository implementation: `sentinel-console/brain/broker-gross-replay.js`.

## Methodology (research assumptions, not course instructions)

Existing `pdf_sweep_bos` and `pdf_fvg_retest` **price-pattern implementations** were replayed using the same strategy decision function `core.decide(..., 'source_only')` as Sentinel's developer branch. For each candidate, use last fully completed broker M15 and fully completed H1 (no future hours). Entry at the **next contiguous M15 bar open**. Price stop = strategy's specified ATR multiple; target = its specified R multiple; time exit after **up to 12 M15 bars**. A stop and target touched within the same bar count as a **stop**. Gaps on stop exits are applied conservatively; do not synthesize nonexistent weekend/session bars. At most one concurrent position per family. A fixed research equity risk of **0.25%** is used only for a comparable hypothetical equity illustration — not a production risk policy.

Market data are split by bar time at **65% chronological development / 35% later out-of-sample**. Any development trade whose exit crosses the later boundary is excluded from training. No fees, spread, swaps, funding, estimated commissions or slippage are subtracted. These figures are NOT net broker earnings and do not validate execution feasibility.

## Observed results

| Instrument | Family | Dev trades | Dev gross R | OOS trades | OOS gross R | OOS gross PF | OOS win % | Hypothetical OOS equity % |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | pdf_sweep_bos | 42 | +1.3409 | 23 | +13.1758 | 2.8422 | 60.87 | +3.3351 |
| EURUSD | pdf_fvg_retest | 6 | +2.7836 | 11 | +0.0645 | 1.0107 | 45.45 | +0.0112 |
| BTCUSD | pdf_sweep_bos | 52 | -0.0397 | 22 | -1.7159 | 0.8404 | 36.36 | -0.4352 |
| BTCUSD | pdf_fvg_retest | 14 | -10.0404 | 6 | +1.3516 | 1.6433 | 50.00 | +0.3361 |
| XAUUSD | pdf_sweep_bos | 0 | 0 | 1 | +0.2940 | n/a | 100 | +0.0735 |
| XAUUSD | pdf_fvg_retest | 0 | 0 | 0 | 0 | n/a | n/a | 0 |
| NAS100 | pdf_sweep_bos | 0 | 0 | 1 | +2.0000 | n/a | 100 | +0.5000 |
| NAS100 | pdf_fvg_retest | 0 | 0 | 0 | 0 | n/a | n/a | 0 |

OOS start: EURUSD **2026-10-30 04:00 UTC**; BTCUSD **2026-10-30 12:00 UTC**; XAUUSD **2026-11-16 20:00 UTC**; NAS100 **2026-11-16 20:30 UTC**.

**Interpretation:** EURUSD Sweep+BOS is a **research candidate** that merits deeper forward verification, not an approved edge. Its 23 OOS trades and weak development expectancy are insufficient for robust promotion. BTCUSD Sweep+BOS was negative OOS. BTCUSD FVG had only six OOS trades after a significantly negative development sample. Gold and NAS100 had only one OOS opportunity and insufficient H1 history. A favorable two-week sample does not establish predictive accuracy.

## Most important data-integrity actions before any release

1. Capture complete MT5 broker open_time, verified broker ticket and immutable **pre-order strategy tag, stop risk, volume and signal version**; do not infer entry facts from the signal's bar timestamp.
2. Use purged and embargoed, account-isolated chronological forward reviews; all missing pre-entry facts must remain excluded. See `broker-evidence-contract.js`, `purged-forward-evidence.js` and future-release migration.
3. Add more matched Fusion M15/H1 history to XAUUSD, NAS100 before evaluating those markets; never substitute Binance BTCUSDT Spot historical trades for Fusion BTCUSD/XAUUSD.
4. Add multiple out-of-sample windows, no parameter fitting on held-out periods, minimum sufficient sample sizes, and a PBO / multiple-trial warning. Paper/DEMO trading remains paused until explicit approval.

Research references:
- https://random-docs.readthedocs.io/en/latest/implementations/cross_validation.html (Purged/embargo cross validation)
- https://escholarship.org/uc/item/4w1110bb (Probability of Backtest Overfitting)
- https://nautilustrader.io/docs/latest/concepts/overview/ (Backtest/live event model principles)

**Reproduction:** An authorized maintainer can export the four instruments' time-ordered M15/H1 from `sentinel_brain_candles` for the same exact Demo account. Then call `require('./broker-gross-replay.js').run({symbol,m15,h1})`. No broker credentials are committed.
