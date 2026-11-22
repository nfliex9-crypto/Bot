# Sentinel Adaptive Intelligence V2 — GitHub development only

**Status:** DEVELOPMENT / RESEARCH-ONLY. **Not deployed to Vercel or Neon.** Do not merge into the live Bot branch or automatically re-enable demo execution.

## Production pause verified on 2026-11-22

FusionMarkets-Demo account ending **1964**: `sentinel_cloud_trader_authorizations.enabled=false` on the existing Neon branch. Five-minute and 15-minute schedule triggers remain enabled. A subsequent scheduled cycle at 2026-11-22 05:27 UTC completed in `SHADOW_ONLY` with `orders_sent=0`. Existing trades, records and monitoring were not deleted.

## Changes in V2 development branch

- `worker/cloud-trader/regime-intelligence.js`: validated, monotonically ordered M15/H1 OHLC; closed-bar efficiency ratio, H1 EMA20/50 direction, M15/H1 ATR, ATR expansion and shock ratio; labels `TRENDING`, `RANGING`, `TRANSITION`, `VOLATILE`, or `UNKNOWN`.
- `worker/cloud-trader/adaptive-risk.js`: explainable quality score for the two existing source-price-pattern families. Calculates proposed risk from directional agreement, candle body, close location, strategy-family tag, market regime, current equity versus day-start equity, and current number of open positions/orders. Unknown/incomplete data, future H1 timestamps, unknown strategies, or adverse H1 direction reject the candidate.
- `worker/cloud-trader/runner.js`: logs regime metrics per symbol even if no entry signal exists; logs decision components and risk factors. **A disabled DB authorization must block new demo orders even if legacy environment flags request execution** (this code change applies on future deployment only).
- Tests: 11 V2 market/risk cases and 2 authorization cases, plus inherited tests. The 11 standalone V2 cases were run locally and passed before committing; GitHub CI validates repository integration.

## Scope and research limitations

These are **hand-designed price-only heuristics**, not empirically calibrated profit probabilities. They do not claim that M15 OHLC contains authentic Delta, executed order flow, DOM, or liquidity-provider intent. The existing PDFs and Orderflows video course must be checked directly before attributing any new rule to those sources. No auto-promotion of candidates into trading.

**Backtest policy:** gross price-only; no simulated spread, commission, swaps, funding or slippage deductions. Broker quotes, contract validity, stop-level and account-margin checks are independent execution safeguards, not deductions. Realized broker fees are historical facts and are not erased from accounting.

No fixed daily order quota, daily 1% stop, or total-position count cap in the adaptive allocation formula. Exposure count and equity deterioration continuously reduce proposed risk. **Broker contract limits, position sizing, exact demo identity, quote validity, order reconciliation, and manual pause remain necessary**. Exposure count is a proxy, not true portfolio value-at-risk. No guarantee of profit or safety.

## Before any deployment

1. Run all repository regression tests on GitHub; fix every failure.
2. Replay real broker M15/H1 history with purged walk-forward/OOS separation and no lookahead. Compare V2 with the previous adaptive allocator; include sample counts, gross R, drawdown, and adverse-regime outcomes.
3. Validate instrument-specific broker contract/tick values and portfolio exposure; test gap/stop-first behavior.
4. Evaluate setup rules from the actual source documents/videos separately. Never substitute guessed Delta rules.
5. Add operator-visible shadow explanations and a rollback switch.
6. **Ask for explicit approval** before a single release. Keep the DB authorization disabled until the owner explicitly requests demo entry resumption.

## Reproduce V2 tests

```bash
node --test sentinel-console/tests/adaptive-intelligence-v2.test.cjs sentinel-console/tests/adaptive-v2-authorization.test.cjs
```

**Deployment policy:** all development on `sentinel-adaptive-intelligence-v2` GitHub branch. No Vercel/Neon deploy, no new broker orders.
