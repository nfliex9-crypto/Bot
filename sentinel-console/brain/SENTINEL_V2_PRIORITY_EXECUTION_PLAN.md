# Sentinel V2 — evidence-first engineering plan (2026-11-22)

**Branch:** `sentinel-adaptive-intelligence-v2`, based on `sentinel-adaptive-demo-risk-v1`. **No production merge, no trading reauthorization, no Neon migration, no Vercel deploy**. GitHub code/tests only. The pre-existing Neon v23 scheduled monitor remains independent and its `FusionMarkets-Demo ••••1964` authorization is disabled. Check live status on the day of review.

## P0 — work that matters before ANY new strategy

| Work item | Status | Evidence / blocking condition |
|---|---|---|
| Account-isolated, pretagged and purged forward testing | IMPLEMENTED / TESTED | `brain/purged-forward-evidence.js`. Chronological 65/35 by trade **opening** time, purge resolved-training labels that overlap OOS, 1h embargo, exclude duplicate tickets, unknown risk, future labels; no auto promotion. |
| Matched broker OHLC replay | IMPLEMENTED / TESTED | `brain/broker-gross-replay.js`. Closed M15 signal, CLOSED H1 context, next contiguous M15 opening, no lookahead, stop-first intrabar, gap handling, development vs OOS. Existing source-pattern families only. |
| Independent EURUSD / BTCUSD / Gold / NAS evidence | INITIAL RESULTS | `brain/backtests/FUSION_MT5_GROSS_REPLAY_2026-11-22.md`. EURUSD sweep +13.1758R in 23 OOS examples is a *candidate*, not a proven strategy. BTCUSD sweep lost OOS. Gold & NAS have one OOS signal each: totally insufficient. |
| True entry-time risk provenance | CODE + FUTURE MIGRATION STAGED | `brain/broker-evidence-contract.js`, `brain/migrations/20261122_sentinel_preentry_evidence.sql`, `worker/cloud-trader/runner.js`. The runner future-release code writes broker-requoted volume, SL/TP, risk and source BEFORE order submission. No historical data retrofitting. **Migration not applied.** |
| Full regression | TESTED | 257/257 Node tests passed in an isolated, non-deployed sandbox after the V2 updates; fix regressions before any final release. |
| Single consistent regime model | IMPLEMENTED / TESTED | `brain/intelligence-v2.js` now uses `worker/cloud-trader/regime-intelligence.js` for matching market labels. No divergent definitions across research and demo. |
| No-go on real-money execution | ENFORCED / MONITORED | Existing Neon authorization false, periodic monitoring continues, no real-money broker route, no automatic candidate promotion. |

## P1 — next highest-value work

1. **Convert verified live Demo outcomes into usable training labels:** check whether TickerAll completed-trade history supplies authentic `openTime` and `openPrice`, along with exact broker ticket and complete flag. Without actual `open_time` and saved pretrade risk, learning remains `COLLECTING`. Do not fabricate missing facts.
2. **Multiple holdouts by date / market regime:** longer real broker history, multiple nonoverlapping OOS windows, sample adequacy, drawdown, ratio of positive/negative calendar weeks. Avoid optimizing thresholds on held-out observations. Report number of tested candidate configurations to assess selection bias.
3. **Portfolio exposure from stop-risk and correlation:** `brain/portfolio-exposure-advisor.js` research code uses matched H1 returns and account-currency risk-at-stop. A simple position count is not a risk measure. Missing contract/risk inputs must block calibration, not default to zero. Correlation can fail in crises; do not treat it as a guarantee.
4. **Order-flow data authenticity:** user-uploaded course demonstrates Delta concepts; actual Footprint must come from a verified executed-trade tape for the **same venue, symbol and time**. Binance BTCUSDT Spot data cannot be relabeled as Fusion MT5 BTCUSD/XAUUSD. Preserve provenance.
5. **Strategy evaluation engine:** validate the existing Sweep+BOS, FVG, trend and composite hypotheses per symbol and regime, consider only candidates that repeat across independent OOS periods. The score is heuristic until actual labeled broker examples support calibration.
6. **Deterministic paper trade management:** forward-test breakeven, trailing exit and early exit as a SEPARATE strategy family with full pretrade version, then compare *gross* out-of-sample R. Never apply untested management rules to existing positions.

## P2 — useful, after evidence

- Dashboard explains source, regime, candidate's reason, risk factors and data quality, with broker snapshots and full decisions.
- Faster candidate discovery and agent experiment bookkeeping, without endless self-generated low-quality strategies.
- Research notes and alerts, historical replay UI, chart cosmetics, optional library integrations.

## External resources checked, but NOT copied or installed

- NautilusTrader — event-driven simulation/live-parity architecture: https://nautilustrader.io/docs/latest/concepts/overview/
- Purged KFold, embargo and CPCV principles: https://random-docs.readthedocs.io/en/latest/implementations/cross_validation.html
- Probability of backtest overfitting — research framework: https://escholarship.org/uc/item/4w1110bb
- Deflated Sharpe paper: https://doi.org/10.2139/ssrn.2460551

These are architecture/research references, not pre-proven MT5 strategies or new market feeds. No private resource outside the owner's authorized accounts is assumed accessible.

## User operating requirements

- XAUUSD, BTCUSD, NAS100 and EURUSD prioritized; long and short, M15 + H1 context now (other frames research separately).
- No invented costs in **research backtests**: spread/commission/swap/slippage deductions remain **zero**. Keep actual historical broker charges intact in broker accounting; do not confuse gross replay with spendable net profit.
- No Martingale, grid, or averaging down; default NO TRADE on unknown state. Position size is dynamic, but SL and broker contract/margin validation remain mandatory.
- Do not modify the separate Grok bot, any live-money account, or the original `Bot` production branch.
- No Vercel/Neon release while the user requested GitHub-only development. Before a *single* final deploy: independent reviews, tests, migration rollback plan, explicit user approval, and explicit reauthorization of Demo entry (separate from code publication).

## How to verify

```bash
cd sentinel-console
npm install --ignore-scripts --no-audit --no-fund
node --test tests/*.test.cjs
```

**Never run against live trading credentials in CI.** For broker replay, obtain only owner-authorized historical OHLC from the named Demo account, export validated ordered M15/H1 bars, and run `require('./brain/broker-gross-replay.js').run({symbol,m15,h1})` offline.
