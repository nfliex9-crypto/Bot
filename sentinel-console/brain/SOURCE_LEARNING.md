# Sentinel — Evidence-Based Source Learning (Research Only)

Updated: 2026-11-20. Development branch: `sentinel-amt-curriculum-v1`.

## What is actually indexed

- **14 owner-supplied AMT / DeepCharts Bootcamp videos**: English auto-caption tracks accessed, 28 timestamped topic pointers. **Audio not audited**, no complete captions committed, no video-specific trade rules certified.
- **8 owner-supplied trading PDFs, 350 pages total**: SHA-256 fingerprints, original filenames, key section/page citations, and nine testable hypotheses. **Key sections reviewed, not every page exhaustively audited.** No PDF bytes or copyrighted full text committed.
- **Price-only source-pattern scanner**: detects local extreme sweeps/reclaims (Turtle Soup proxy), 3-bar wick non-overlap (FVG proxy), and body displacement beyond a prior range. Uses only *closed* OHLC bars and no future data at signal time.
- **Edge Lab OOS experiment**: tests a separate FVG first-retest candidate alongside sweep/reclaim and compression breakout, using fixed chronological train/validation/holdout. It uses a recent real quote P90 **cost proxy**, not genuine historical spreads or complete execution costs.
- **Research worker integration**: `worker/runner.js` computes source-pattern counts and descriptive 4-bar follow-through on cached M15 broker candles; results are included in research cycle notes when the new worker version is deployed.
- **Dashboard**: read-only source registry, evidence timestamps, missing-data gates, PDF page pointers, and research observations if present.

## Source-derived hypotheses and what they require

| Hypothesis | Primary source | Research state |
|---|---|---|
| Turtle Soup / local sweep and reclaim | Wade FX pp. 80–81; Types of Liquidity p. 9 | Price-only scanner + cost-proxy Edge Lab |
| Stop hunt → BMS → RTO | Wade FX pp. 87–88 | Sequential HTF/LTF detector pending |
| Failure swing → BMS → RTO | Wade FX pp. 93–94 | Sequential detector pending |
| 3-candle FVG / imbalance | Price Action Imbalance pp. 2–3 | Scanner + OOS first-retest candidate |
| HTF supply/demand + double LTF BOS | Entry Types Part 1 pp. 2–4 | Requires synchronized multi-timeframe history |
| Corrective break vs displacement | Entry Types Part 2 pp. 2–3 | Body/range price-only proxy |
| Consolidation → expansion → retest | Supply and Demand pp. 2–4 | Stateful zone definition pending |
| Kill zones / AMD | ICT & MMM Notes pp. 43–45 | Verified exchange session calendar and DST handling pending |
| SMT divergence | ICT & MMM Notes pp. 23–24 | Correlated, synchronized instrument feeds pending |

**Do not confuse** inferred liquidity from equal highs/lows with verified stop orders. **Do not infer** Footprint, CVD, aggressor-side volume, or genuine Volume Profile from MT5 OHLC or tick volume.

## Evidence-promotion contract

1. A source reference must have a stable ID, page/timecode, and an explicit objective rule with no future lookahead.
2. Verify sufficient broker candle coverage, historical bid/ask (or a clearly labelled cost proxy for preliminary research), and symbol-specific contract settings.
3. Run disjoint train/validation/untouched holdout and rolling walk-forward; include parameter sensitivity and cost stress. Avoid picking a strategy from holdout.
4. Shadow/forward test with timestamped signals and actual demo broker fills. Record adverse excursions, net R, commissions, slippage and regime.
5. Independent review before **any** strategy is eligible for demo execution. **Never** automatically promote a PDF/video claim or adjust risk based on source prestige.

**No production Bot branch changes, no live-money orders, no user-supplied PDF redistribution.** GitHub CI validates syntax, provenance, deterministic signals, no lookahead and execution isolation.

## Next materials worth sourcing legally

1. **Actual futures order-flow/Footprint and Delta course** with tick/trade samples, executed bid/ask, absorption, CVD, and session examples (GC for gold and NQ for Nasdaq). DeepCharts exercises or equivalent with downloadable sample data are especially useful. A PDF without raw market data cannot verify these signals.
2. **James Dalton — Mind Over Markets** or equivalent AMT/Market Profile material to formalize TPO, value area, initiative/responsive activity and auction context. Obtain a licensed copy.
3. **Marcos López de Prado — Advances in Financial Machine Learning** or an equivalent reproducible quantitative validation curriculum (purged cross-validation, backtest overfitting, event labeling). This improves evidence quality, not entry signals by itself.
4. **Historical broker bid/ask candles/ticks** for Fusion Demo symbols, especially XAUUSD and BTCUSD. This is the immediate technical bottleneck, more important than collecting another hundred indicators.

## Deployment status

The GitHub branch and tests are independent from the currently deployed research worker. A passing CI test **does not mean** the live Neon function has been upgraded. Verify a new deployment and real cycle notes before claiming continuous source-based learning is active.
