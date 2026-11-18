# Sentinel Quant Ecosystem Integration — Research v3
Date: 2026-11-18 · Branch: `sentinel-console-isolated-v1` · Scope: **research only**

This is a source-grounded integration audit and *implemented* upgrade. The repositories supplied by the user differ in runtime, language, dependencies, licensing and purpose; they are not one drop-in MT5 bot.

## What is actually implemented

1. **Daily-block bootstrap / multiple-testing gate** — `brain/robustness.js` is a deterministic, original Node.js implementation. It resamples **distinct UTC trading days** rather than treating every correlated intraday trade as an independent observation. It uses a one-sided Bonferroni adjustment (`alpha=0.05/4`) for the four fixed historical strategies, 512 seeded bootstrap samples, and a minimum of 12 trading days. An existing apparent OOS candidate is moved to `MULTIPLE_TESTS_UNCERTAIN` unless the corrected lower bound remains positive.
2. **Realistic research boundaries** — Existing `brain/engine.js` retains chronological, disjoint OOS folds, next-bar entries, stop-first same-bar ambiguity, and 2× cost stress. *No* strategy can be automatically deployed from these statistics. Block bootstrap is an additional guard, not proof against all multiple-testing/selection effects.
3. **Dataset fingerprint / reproducibility** — `brain/provenance.js` computes a SHA-256 fingerprint across strictly chronological broker candles, broker source, symbol, timeframe, spread and tick volume, and `api/brain.js` saves it in the research run analysis. This makes differing market-data inputs visible across reruns and strengthens auditability.
4. **Dashboard evidence** — `brain-ui.js` displays independent days, multiple-testing-adjusted lower confidence bound, and a short dataset fingerprint. Unknown/null metrics display `—` instead of a deceptive zero.
5. **Automated tests** — `tests/quant-robustness.test.cjs` covers correlated intraday days, strong/weak evidence, deterministic resampling, rejection of non-finite or out-of-order bars, and **no order execution**; GitHub Actions runs them alongside existing MT5 isolation, broker API and SSO tests.

## Exact upstream references and scope

| Upstream source | Confirmed role from repository | Sentinel integration status |
| --- | --- | --- |
| [perspective-dev/perspective](https://github.com/perspective-dev/perspective) | High-throughput streaming, pivoting, visualization, WebAssembly viewer | **Architecture reference** for future interactive datasets. Not bundled or loaded on the current site (would require an audited frontend dependency/build and CSP changes). |
| [openbq-org/OpenBB](https://github.com/openbq-org/OpenBB) | Open Data Platform with Python/REST/MCP and multiple provider integrations | **Data-provenance reference**. No OpenBB API/provider account connected; actual research candles still come from TickerAll Demo. License varies by project parts; do not copy upstream code without review. |
| [microsoft/qlib](https://github.com/microsoft/qlib) | AI-oriented quant research, experiment recording and modeling | **Research-validation reference**; no Qlib runtime or model training deployed. New unreleased Qlib artifact-loading trust model must be considered before installing. |
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | Event-driven modular backtest/live trading engine | **Execution-semantics reference** only; no LEAN instance or MT5 brokerage adapter installed. Current Sentinel engine remains a simpler isolated simulator. |
| [stefan-jansen/machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading) | End-to-end ML workflow, evidence boundary, OOS/forward validation and monitoring | **Methodology used in new v3 research gate**. No notebook/models copied. |
| [ml4t/backtest](https://github.com/ml4t/backtest), [ml4t/data](https://github.com/ml4t/data), [ml4t/models](https://github.com/ml4t/models) | Separate event-driven backtester, market data validation, and finance-native ML libraries | **Methodology and modular boundaries used**; Python 3.12+ packages not installed in the Node/Vercel runtime. The user-provided `github.com/ml4t` is an organization, not one repository. |
| [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) | Trainable, reusable LLM agent instruction skills with validation gates | **Future agent policy option**, not an MT5 order engine. No optimizer or autonomously rewritten trading instructions running. |

**No upstream source code was vendored.** The new modules were authored locally for Sentinel using the open-source repos as research and architectural references.

## Hard evidence limits

- The active bot authored inside **Grok** is **not** independently identified as this legacy repository. These commits only update Sentinel Intelligence and cannot claim to change the currently trading Grok/MT5 bot.
- As last checked on 2026-11-18, Neon held 0 imported broker trade rows, 0 broker candle rows and 0 saved research runs, even though a TickerAll API token was configured. No live market-based result or profitability claim is available yet.
- Run the existing **Intelligence** page's broker-history import and research pipeline against a Demo account to create results. If the broker symbol is absent or coverage/spread is incomplete, result stays data-limited. History permissions and TickerAll Free cooling can block imports.
- The original broker stream is not proof that strategy trades have been tagged before entry. Do not promote a strategy from untagged broker profit.
- **Daily-block bootstrap is not a universal correction** for data snooping across many symbol/timeframe searches, overnight correlated exposures, regime changes, or researcher discretion. The corrected lower bound is a research gate, not a forecast or guarantee.
- The current product places **no orders**, does not host a permanent strategy loop, and does not ensure zero-cost 24/7 operation. Live accounts remain forbidden.

## Next upgrades (NOT yet implemented)

1. Broker-grade data ingestion with actual historical spread, contract/tick value and provenance (OpenBB is a secondary data option, not an MT5 execution replacement).
2. Train/validation/test dataset and model registry with time-series embargo and delayed labeling (Qlib + ML4T; no training on synthetic data or in-sample-only metrics).
3. Independent execution parity test with LEAN on a supported brokerage; do not equate its fills with MT5 until adapter and costs are verified.
4. Optional self-hosted Perspective viewer for large imported trade/candle tables, tested for CSP and mobile memory use.
5. SkillOpt-style agent skill candidate vs champion behind **held-out replay validation**; no self-editing of live trade instructions.
6. Verified connection to the *actual* Grok trading bot's source/strategy IDs, followed by an explicitly Demo-only authenticated worker with broker reconciliation, independent uptime monitoring and capped costs.

## Verification

```sh
node --check sentinel-console/brain/robustness.js
node --check sentinel-console/brain/provenance.js
node --test sentinel-console/tests/quant-robustness.test.cjs
node --test sentinel-console/tests/brain.test.cjs
```

The GitHub Actions workflow `.github/workflows/sentinel-console-check.yml` runs this suite plus existing boundary tests. Vercel Hobby deployment quota may still block promotion of new commits. Treat repository updates and a production **READY** deployment as distinct states.
