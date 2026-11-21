# Sentinel — 0-deduction composite strategy research backtest

**Date:** 2026-11-21. **Branch:** `sentinel-delta-composite-research-v1`. **Execution:** research only; no broker orders.

## Important instruction and scope

All **simulated** cost deductions and synthetic spread/fees/slippage are disabled in this research branch. No input price is shifted for spreads; entry at next full bar open; exits use unadjusted levels. Profit factor, gross R, and hypothetical compounded returns are **gross before transaction costs**. Broker-provided actual fee/swap records and Demo quote/contract safety checks are **not altered or falsified**.

## Real underlying input data

Public Binance Spot BTCUSDT **aggregated executed trades (aggTrades)**, buyer-maker flag used for taker direction. 10 UTC dates:
- **TRAIN**: 2026-10-20 to 2026-10-24 (five consecutive days)
- **OOS**: 2026-11-13 to 2026-11-17 (five later consecutive days)

**12,081,050 aggregated trade rows**, 2,880 M5 and 960 M15 reconstructed bars. Official archive SHA-256 verified for all 10 dates. Venue differs from FusionMarkets MT5 and futures. Hypothetical shorts are **not** real Binance Spot shorts.

## Immutable researcher-defined conditions (not verbatim source rules)

- **Sweep + Delta Divergence + BOS:** previous 12-bar high/low sweep and reclaim, adverse/signed delta at sweep in the divergence direction with a 6-bar lookback, then closed-bar break beyond sweep-bar extreme within four candles. Any price invalidation cancels the pattern.
- **Trend + Delta Surge:** H1 closed-hour EMA20 versus EMA50 alignment (70 full hourly bars), 4-bar surge visual-example delta sequence, and a close beyond 6-bar previous high/low in the trend direction.
- Closed signal bar only. Next bar open entry. SL=1.5 ATR14; TP=2R. Stop-first for same-bar SL/TP; at most 12 bars holding. Hypothetical per-trade risk 0.25% equity. No fees, swaps, spread, slippage, funding or other friction of any kind.
- One position per family. Chronological separation. No automatic model selection using OOS data. These parameters are explicitly research choices and not universally prescribed by the video course.

## Gross results

| Timeframe | Split | Family | Trades | Win % | Total gross R | Profit factor | Hypothetical equity change (%) |
|---|---|---|---:|---:|---:|---:|---:|
| M5 | TRAIN | sweep_divergence_bos | 32 | 53.13 | +12.5526 | 1.9659 | +3.1688 |
| M5 | TRAIN | trend_delta_surge | 3 | 66.67 | +3.0000 | 4.0000 | +0.7500 |
| M5 | OOS | sweep_divergence_bos | 24 | 29.17 | -10.5460 | 0.3191 | -2.6085 |
| M5 | OOS | trend_delta_surge | 3 | 0.00 | -2.0845 | 0.0000 | -0.5204 |
| M15 | TRAIN | sweep_divergence_bos | 11 | 36.36 | -1.1132 | 0.8003 | -0.2821 |
| M15 | TRAIN | trend_delta_surge | 1 | 100.00 | +2.0000 | n/a | +0.5000 |
| M15 | OOS | sweep_divergence_bos | 2 | 100.00 | +2.0228 | n/a | +0.5057 |
| M15 | OOS | trend_delta_surge | 0 | n/a | 0.0000 | n/a | 0.0000 |

**Interpretation:** M5 sweep strategy went from positive TRAIN (+3.17%) to negative OOS (-2.61%), despite zero transaction deductions. M5 trend+surge OOS lost with only three trades. M15 two wins are far too few to establish edge. No strategy earns DEMO promotion on these data.

## Reproduce

1. Run `python3 sentinel-console/worker/orderflow/binance-aggtrades-bars.py bars.json` (downloads and checks official daily archive SHA-256).
2. Run `node sentinel-console/worker/orderflow/composite-backtest.cjs bars.json > composite-results.json`.
3. Verify metrics and research-only status. No credentials required; never deploy this script to order routing.

Official Binance public data: https://github.com/binance/binance-public-data

**Boundary:** Historical broker fee/swap columns in actual execution records are retained as facts. Gross scoring policy in this isolated branch ignores them for strategy choice, but must not be presented as actual net account profit. The earlier cost-inclusive research report is an archived past scenario, not the current gross-only method.
