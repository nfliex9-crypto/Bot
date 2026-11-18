# Sentinel Adaptive Brain v2 — Audit & Engineering Contract

Updated: 2026-11-18. Isolated branch: `sentinel-console-isolated-v1`.
**Never assume this repository is the separate Grok bot. No production Bot branch or live broker execution is modified.**

## Verified state (read-only audit)
- Neon project `sentinel-mt5-connect` has the schema for trades, candles, order tags, imports and runs, but as of audit: **0** stored trades, **0** historical candles, **0** tags, **0** analysis runs and **0** imports.
- TickerAll Demo can show ONLINE independently of delayed broker account balance. A connected provider is not proof of working trading execution.
- Sentinel `api/free-mt5.js` and `api/brain.js` contain **no trade placement endpoints**. No unattended MT5 execution worker is deployed by this project.
- The old Python `app/training/trainer.py` scales the entire dataset before shuffled cross-validation and can generate misleading ML validation results; it is not the active Sentinel learning path. Its synthetic bootstrap and approximate pip sizing must not be promoted to live or demo performance evidence.
- Vercel Hobby quota previously blocked manual production deploys. Development branch auto-preview deployments are disabled; no deployment is claimed until Vercel confirms READY for the latest commit.

## New v2 intelligence
1. **Real data memory:** owner-triggered MT5 Demo history and OHLC imports are stored idempotently in Neon. The Intelligence page opportunistically catches up at most once every six hours while open and broker ONLINE; it does **not** run in the background when closed. The user can run the full pipeline manually.
2. **All-trade broker memory:** every completed MT5 trade, even without a strategy tag, contributes to descriptive performance by symbol, BUY/SELL direction and UTC trading session. This identifies underperforming markets or time windows for further **paper research**, without falsely attributing trades to an algorithm. Fees may be incomplete.
3. **Chronological research:** four fixed strategies evaluated on three disjoint out-of-sample periods. Entry is next-bar open; exit includes stop-first ambiguity handling and double-cost stress. Incomplete candle history or insufficient spread data cannot promote a candidate.
4. **Regime lab:** simulated OOS trades are segmented into trending, ranging, volatile and transition conditions. A regime with fewer than 12 samples is LOW_SAMPLE; negative expectancy after cost stress is AVOID_PAPER.
5. **Forward learner:** only completed, broker-reported trades attributed to a strategy **before closing** and with recorded entry risk can influence forward rankings. Training is separated by broker account and symbol, with duplicate rejection and timestamp checks. An untagged trade is remembered for account-level statistics but cannot train a specific strategy.
6. **Anti-overfit controls:** capped learning outcomes at +/-5R (raw broker results unchanged); cost stress of 0.15R; correlated intraday trades evaluated by distinct calendar days; a 95%-style one-sided daily confidence bound; recency weighting; early/recent stability; outlier concentration and recent drawdown/deterioration checks.
7. **Automatic research allocation:** persistent negative performers get PAUSE_PAPER_RESEARCH; recent deterioration gets PAUSE_PAPER_RESEARCH_DRIFT; only strategies with >=40 qualified trades across >=10 days, robust positive forward results and other quality criteria can receive BOOST_PAPER_RESEARCH_2X. This **doubles research priority, not lot size or money at risk**. Multiple families receive a 65% cap where possible.
8. **Source and scope honesty:** history endpoint currently requests up to 5000 records; more may exist. Imported candle batches are capped at 10000, and provider truncation blocks promotion. Forward tags do not reliably include timeframe, so forward evidence is **symbol-scoped**, not timeframe-confirmed.

## Gaps before autonomous demo trading
- The active Grok/MT5 execution bot source is not proven to be `nfliex9-crypto/Bot`.
- No trusted bot-side **pre-trade strategy ID, risk, symbol, timeframe and ticket** emitter is integrated with Sentinel; existing `tagPosition` requires a Demo position opened within two minutes and is not automatic.
- No authenticated always-on worker/cron or proven 24/7 free provider session is available. TickerAll Free may cool when idle.
- Broker costs, contract sizes, tick values, and complete history coverage must be verified against the actual MT5 Demo broker before using research to size orders.
- There is **no guarantee of profitability**; OOS research is not forward trading evidence. No capital/risk scaling is enabled.
- Do not expose the legacy Python backend's unauthenticated control routes to the internet.

## Release checklist
1. GitHub Actions: all syntax, unit, integration, SSO and bridge smoke tests green.
2. Confirm Vercel Hobby deployment quota reset; perform **one** production deployment of the latest isolated branch.
3. Confirm production SHA and the protected console URL.
4. Open Intelligence with TickerAll Demo ONLINE; check actual import counts and completeness.
5. Re-evaluate XAUUSD/GOLD, EURUSD, NAS100, BTCUSD **only where the broker lists those symbols**.
6. Integrate verified bot-side pretrade tagging and a demo-only worker as a separate explicitly authorized phase. Keep all live accounts blocked.

No secrets or MT5 credentials are included in this file.
