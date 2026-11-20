# Sentinel source-driven MT5 DEMO signals — 2026-11-20

Branch: `sentinel-source-execution-v1`. **NOT a production Bot deployment**. No live-money account writes; no broker trade receipts were created in this change.

## What is actually wired into the broker-side decision path

The private `worker/cloud-trader/runner.js` calls `c.decide(...,"source_only")` for every closed M15/H1 broker-candle pair. This disables the old EMA-pullback/Donchian fallback **in this branch**: if no source-derived setup exists, the result is no trade. The shared DEMO-only preflight, position/order guard, contract risk sizing, idempotent order journal, broker-fill reconciliation and daily account lock remain in force.

Implemented independent setups:

1. `pdf_sweep_bos` — based on owner PDFs: *Wade FX Market Structure* physical pp. 80–81, 88 and *Types of Liquidity* p. 9. Detect an M15 previous-low/high penetration with reclaim, then on the **following closed bar** require a close beyond that sweep bar in the H1 EMA20/50 direction. Excludes equal-high stops as observed order book data.
2. `pdf_fvg_retest` — based on owner PDF: *Price Action Imbalance* physical pp. 2–3. Record a three-candle wick non-overlap, require the **first** closed-bar rejection/retest within the next 3–26 M15 bars, and align with H1 EMA20/50. Prevents duplicate entry using signal family, side, account, symbol and signal-bar time.

All source entries have explicit family, timestamp, PDF page references and `edge_verified:false`. No video is misattributed as a source rule.

## Nine source hypotheses remain in the research registry

The original eight-PDF, 350-page corpus remains in `brain/pdf-curriculum.js`. Of the nine indexed research hypotheses, only the **two above** have been connected to the private DEMO entry decision route. Displacement is observed in the research scanner but not authorized as a separate entry family. Stop hunt → BMS → RTO, failure swing → BMS → RTO, higher-timeframe supply/demand double BOS, full consolidation/expansion retest, session AMD/kill zones, and cross-symbol SMT require additional deterministic detectors and/or synchronized data, so are **not** trade-enabled.

The 14 AMT/DeepCharts bootcamp auto-caption timestamps were indexed, not end-to-end audited; none has been promoted to an executable trading rule.

## Execution and validation

- Run: `node --test sentinel-console/tests/source-demo-signals.test.cjs`.
- CI workflow is configured on the isolated branch and includes those tests plus legacy trader tests.
- Authorized **DEMO** orders still require the existing exact account identity, time-limited database/worker authorization and broker validations. A GitHub commit or Vercel build does **not** automatically deploy the private Neon worker, change its environment, authorize DEMO orders, or prove a broker fill.
- Never set `SENTINEL_CLOUD_MODE=demo_execution` against any account marked Live, or treat unvalidated PDF setups as profitable. A successful deployment only permits the next independently authorized DEMO validation.

## Before a source setup is an approved strategy

1. Verify Fusion DEMO feed returns complete, properly aligned broker M15 + H1 closed candles.
2. Run walk-forward/OOS with historical bid/ask, commissions, slippage, and enough independent events; no lookahead, multiple-test correction and stress.
3. Confirm the existing private worker actually runs this branch, and observe its source strategy/family/page tags in broker-cycle telemetry.
4. Only in a separately authorized Fusion DEMO session, verify a genuine broker order receipt, linked position, stop/target, final closed deal and net fees.
5. Approve or reject each setup using forward net outcomes; failures should disable that family until reviewed.

## Order-flow ZIP intake specification (1.4 GB)

Keep original raw files (tick-by-tick trades, venue/timezone, bid and ask, aggressor labels, DOM/L2 snapshots, symbol mapping and UTC timestamps if present). Document each file's data source/permission/retention and generate SHA-256 manifest before ETL. Never infer real aggressor delta or resting liquidity from MT5 candles or broker tick volume. Do not commit raw proprietary data to GitHub or public Vercel assets. Missing labels make a price-pattern proxy, not verified Footprint/CVD/absorption.

The large archive has **not been supplied to the development tool yet**, so no L2/DOM/CVD/Footprint strategy has been validated or enabled.
