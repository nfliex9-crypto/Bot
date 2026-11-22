# Sentinel V2 — stored MT5-linked OHLC gross research replay (2026-11-22)

**Research only.** No broker order was sent, no Neon migration applied, no Vercel deployment performed. The production Fusion Demo authorization remains disabled.

## Input / data boundaries

- Read-only query from existing Neon `sentinel_brain_candles`, selecting one common account_id for all instruments (account ID not copied to this report). The table is account-linked, but **does not contain an independent per-bar exchange/broker source attestation**. Do not claim verified executed-trade tape or authentic order-flow from OHLC.
- Rows examined: BTCUSD **5,939 M15 + 3,004 H1**, EURUSD **4,320 M15 + 2,180 H1**, XAUUSD **1,073 M15 + 111 H1**, NAS100 **1,066 M15 + 109 H1**.
- Source hypotheses: existing `worker/cloud-trader/source-signals.js` PDF-derived price-pattern detectors (`pdf_sweep_bos`, `pdf_fvg_retest`). These are **not proven alpha**. Adaptive V2 uses the actual `adaptive-risk.js` gating logic, and never exceeds the configured 0.25% ceiling.
- Engine: `brain/broker-gross-replay-v2.js` (same committed code used for the calculation). Evaluate only closed M15/H1 bars; hypothetical entry next M15 open; SL from signal ATR and stop multiple; TP from signal reward multiple; 12-M15-bar time exit; no same-symbol overlapping trades; adverse gaps at bar open; stop-first when SL and TP touch in one candle. Skip missing recent bars and incomplete trade windows.
- Chronological **70% / 30%** bar split with 12-bar embargo around training boundary. Not a fully independent unseen test: research hypotheses and engineering choices existed before this report, and the same OOS has now been inspected. No optimization was run during this replay.
- **Gross research only:** NO simulated spread, commissions, swaps, funding, slippage or fees. Broker-realized net P/L cannot be inferred. Reported equity returns are **hypothetical compounding** from gross R and assumed sizing, not account statements.
- `asOf` cutoff 2026-11-22 07:00 UTC; OOS start BTCUSD 2026-11-03 14:15 UTC, EURUSD 2026-11-03 10:00 UTC, XAUUSD 2026-11-17 10:30 UTC, NAS100 2026-11-17 11:00 UTC.

## Primary 12-bar OOS results

| Symbol | Mode | OOS trades | Distinct entry days | Win % | Gross total R | Gross expectancy R/trade | Hypothetical gross equity % |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSD | Source only | 24 | 14 | 37.50 | +0.16126 | +0.00672 | +0.03192 |
| BTCUSD | Adaptive V2 | 17 | 13 | 29.41 | -4.99338 | -0.29373 | -0.58816 |
| EURUSD | Source only | 23 | 14 | 60.87 | +14.70551 | +0.63937 | +3.72966 |
| EURUSD | Adaptive V2 | 19 | 12 | 63.16 | +12.70551 | +0.66871 | +1.69951 |
| XAUUSD | Both | 0 | 0 | — | 0 | — | 0 |
| NAS100 | Both | 1 | 1 | 100 | +2.00000 | +2.00000 | +0.50 / +0.26104 |

The NAS100 one-trade result is statistically meaningless; XAUUSD's H1 history is insufficient for the required warmup. BTCUSD Adaptive V2 **underperformed**, and EURUSD results do not establish future profitability. Gross equity returns are lower in Adaptive V2 partly because the allocator uses less than the maximum authorized risk.

## Primary 12-bar training comparison

| Symbol | Mode | Train trades | Gross total R | Gross expectancy R/trade |
|---|---|---:|---:|---:|
| BTCUSD | Source only | 67 | -12.16872 | -0.18162 |
| BTCUSD | Adaptive V2 | 46 | -11.56345 | -0.25138 |
| EURUSD | Source only | 44 | -0.75254 | -0.01710 |
| EURUSD | Adaptive V2 | 38 | +1.33883 | +0.03523 |

## Exit-horizon sensitivity and day-block lower bounds

Using the same chronological OOS and gross-only engine, with time exits 6 / 12 / 24 bars and matching embargoes. Lower bounds are from 1,024 deterministic daily-block bootstrap samples with **assumed 8 screened comparisons** (one-sided alpha 0.05/8 = 0.00625). The actual historical number of searched ideas is **not verified**, so these are **exploratory diagnostics, not adjusted proof of edge**.

| Symbol | Mode | Exit bars | OOS trades | Gross total R | Bootstrap lower daily mean R |
|---|---|---:|---:|---:|---:|
| BTCUSD | Source | 6 | 24 | -1.01672 | -0.49369 |
| BTCUSD | Adaptive | 6 | 17 | -3.19029 | -0.59047 |
| BTCUSD | Source | 12 | 24 | +0.16126 | -0.55574 |
| BTCUSD | Adaptive | 12 | 17 | -4.99338 | -0.76831 |
| BTCUSD | Source | 24 | 23 | +9.70439 | -0.34087 |
| BTCUSD | Adaptive | 24 | 16 | +2.32739 | -0.64028 |
| EURUSD | Source | 6 | 23 | +16.65414 | +0.26139 |
| EURUSD | Adaptive | 6 | 19 | +13.44297 | +0.17697 |
| EURUSD | Source | 12 | 23 | +14.70551 | +0.04616 |
| EURUSD | Adaptive | 12 | 19 | +12.70551 | +0.10793 |
| EURUSD | Source | 24 | 23 | +20.57926 | +0.23366 |
| EURUSD | Adaptive | 24 | 19 | +18.57926 | +0.28692 |

**Interpretation:** BTCUSD lacks a robust positive lower bound in these windows, including the seemingly profitable 24-bar source result. EURUSD is a research lead worth further untouched forward validation, not a live/demo release authorization. Multiple comparisons, session gaps, short OOS duration, venue-specific broker execution and missing cost data remain unresolved.

## Engineering decisions

1. **Do not enable BTCUSD Adaptive V2 entries.** Research and redesign the BTC filters; current evidence does not justify activation.
2. **Keep EURUSD in research priority**, but do not automatically promote, increase risk or send demo orders. Require a new, later forward period and an auditable hypothesis-screening count.
3. **Improve XAUUSD and NAS100 H1 coverage** before ranking these strategies; zero/one trade is not validation.
4. Maintain read-only monitoring; collect true pre-entry risk/strategy lineage before trusting any forward learner. The V2 SQL migration is staged on GitHub and not applied to Neon.
5. Continue the priority order: data provenance > robust OOS > strategy evolution > optional dashboard polish.

## Reproducibility

- Code: `sentinel-console/brain/broker-gross-replay-v2.js`
- Source detector: `sentinel-console/worker/cloud-trader/source-signals.js`
- Adaptive gate: `sentinel-console/worker/cloud-trader/adaptive-risk.js`
- Bootstrap: `sentinel-console/brain/robustness.js`
- Read-only dataset: `sentinel_brain_candles` from the **same** account ID per symbol/timeframe, ordered by `bar_time`. This report does not export account IDs or any credential. The raw historical dataset is not committed, so this is **code-reproducible with authorized DB access**, not a self-contained frozen dataset.
