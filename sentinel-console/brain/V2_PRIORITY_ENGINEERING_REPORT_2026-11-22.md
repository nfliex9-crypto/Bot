# Sentinel Adaptive Intelligence V2 — Priority engineering report
**Date:** 2026-11-22. **Branch:** `sentinel-adaptive-intelligence-v2` in `nfliex9-crypto/Bot`.
**Scope:** GitHub-only research/development. NO Vercel production release, NO Neon migration, NO MT5 new order permission.

## Verified live baseline (read-only checks)
- FusionMarkets-Demo account ending 1964: `sentinel_cloud_trader_authorizations.enabled=false` since 2026-11-22 05:26:35 UTC.
- Observed 05:47, 05:52 and 05:57 UTC cycles: `SHADOW_ONLY`, `COMPLETED`, `orders_sent=0`.
- Existing Neon `sentinel_cloud_trader_intents` has 12 columns and `sentinel_cloud_trader_fills` has 11; V2 pre-entry columns do **not** exist yet. They must be migrated only in a separately approved release.
- The existing live Neon function was not redeployed.

## Priority P0 — broker correctness and hard release gates (implemented on GitHub)
1. Corrected malformed PostgreSQL dollar-quoting in `brain/migrations/20261122_sentinel_preentry_evidence.sql`. Migration is staged, NOT applied.
2. Added `worker/cloud-trader/execution-gates.js`: verifies all required pre-entry ledger columns and the evidence view; fails closed if missing. Rechecks the exact Fusion DEMO DB authorization immediately before broker POST; revocation stops submission.
3. Added `worker/cloud-trader/market-integrity.js`: checks chronological, closed, grid-aligned M15/H1 bars; flags missing recent bars; compares H1 OHLC against four broker M15 candles with verified tick-size tolerance. If data fail, V2 research ranking is withheld. Existing monitoring continues. No fake market closures or orderflow.
4. Capped `worker/cloud-trader/adaptive-risk.js` proposed percentage to **no more than the explicit authorized base risk percentage**, while retaining continuous de-risking for weaker setups, exposure and equity drawdown. A heuristic score is not permission to exceed an authorized risk ceiling.
5. Kept `runner.js` execution unchanged in the deployed backend; all changes exist only in this development branch.

## Priority P1 — evidence-based strategy evolution (implemented as research-only)
- `brain/experiment-selector-v2.js`: uses only pre-tagged, completed, broker-verified DEMO trades and recorded entry risk. Purges training outcomes overlapping held-out OOS, then uses a **daily-block bootstrap** and Bonferroni correction for multiple screened hypotheses. A verified experiment-count ledger is required before even a research-priority label.
- Strong OOS evidence produces `RESEARCH_PRIORITY_FOR_MANUAL_REVIEW`, **never an order, strategy auto-promotion, lot-size increase or broker authorization**.
- A deteriorating OOS candidate becomes `REJECT_OR_REWORK`. Missing data becomes `NEEDS_MORE_VERIFIED_FORWARD_DATA`.
- No modeled transaction-cost deductions in gross research; historical broker facts remain intact.

## Tests and verification
- Seven market-integrity tests passed in a pure-JS local harness.
- Four release-gate tests passed in a pure-JS local harness (authorization logic was stubbed for local isolation; GitHub CI uses the real core module).
- Seven experiment-selector tests passed in a pure-JS local harness.
- Two property-style risk invariants passed, including 200 distinct synthetic scenario checks.
- GitHub Actions CI runs repository tests on branch pushes; consult the latest run for complete integration status. **Synthetic tests are not a profitable backtest.**

## P2 — next major engineering work (NOT yet complete)
1. Build an immutable hypothesis registry with strategy version, parameter search count, broker data fingerprint, training/OOS cutoff and decision lineage.
2. Collect instrument-matched Fusion MT5 closed M15/H1 history and broker fills with pre-entry evidence. Without these, genuine forward performance cannot be learned.
3. Test regime-specific models on gold, BTCUSD, EURUSD and NAS100 individually, using purged walk-forward OOS and untouched final holdout; reject overfit candidates.
4. Introduce separate executed-trade Order Flow feeds only where venue and instrument match. Do not label OHLC as Delta or claim Binance Spot BTCUSDT is Fusion BTCUSD.
5. Build a research scheduler that proposes new **testable** hypotheses and retires weak ones, without automatic demo execution. An always-on V2 research scheduler has **not** been deployed.

## P3 — later
Dashboard aesthetics, animations, nonessential indicators, notification polish and layout refinements. None should precede data correctness or measured strategy quality.

## Release policy
Do not deploy to Vercel/Neon, modify the active production Bot branch, restart trading, change Fusion permissions, or submit any new MT5 orders without explicit owner approval. Source PDFs and Orderflows videos remain distinct evidence; unpublished or private materials require authorized access and must not be invented.
