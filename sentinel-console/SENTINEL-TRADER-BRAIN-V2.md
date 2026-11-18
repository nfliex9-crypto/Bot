# Sentinel Independent Trader — Brain + Order Book integration (development only)

**Date:** 2026-11-18. **Repository:** `nfliex9-crypto/Bot`, development branch `sentinel-independent-trader-v1`.

This changes **Sentinel's** independent Windows MT5 DEMO execution service, **not the Grok trading bot**. No Vercel deployment, real trades, VPS installation, account login, broker execution or new cloud credential has been performed by this development task.

## Implemented

1. `sentinel_trader/brain_gate.py`: local decision gateway linking a closed-bar `trend_pullback` or `donchian_breakout` signal to a **time-bounded, explicit Sentinel research evidence manifest**, matched by *exact* separate DEMO account number and server, market, M15 timeframe and family. A research candidate must have minimum chronological validation/holdout/forward sample sizes; strictly positive out-of-sample and forward expectancy plus worst-cost evidence, and broker-cost/operator-review markers. Missing/expired/inconsistent evidence **blocks DEMO order submission**. These fields are locally provided claims, not independently verified by the service; do not forge or self-promote them.
2. An alternative **explicit, unvalidated DEMO research trial** is available with `strategy_policy=demo_trial`. It requires the independent DEMO account, the existing activation secret, **and** a second local environment switch. This does **not** assert profitability or make it suitable for live money. The distributed config defaults to `research` + `verified_only` and has an intentionally invalid account ID.
3. `sentinel_trader/orderflow.py`: read-only `market_book_add/get/release` support with cleanup, broker-specific L2 bid/ask levels, imbalance, microprice, sample-count and a persistence diagnostic. Unknown/missing/crossed DOM cannot be replaced with synthetic data. `orderbook_mode=observe` reports diagnostics only; `confirm` prevents new DEMO entries unless 5 consecutive samples over 20 seconds match the signal direction. This threshold is **not validated alpha** and is only an optional research filter. Broker CFD/FX DOM is not a consolidated market order book, and no trade-print flow, iceberg detector or external exchange feed is connected.
4. `Journal.research_decision`: durable SQLite one-record-per-signal decision history including Brain and DOM blockers, **separate** from broker order intents, deals or realized P&L. Repeated polling updates a research decision without multiplying trades.
5. Bridge telemetry and console tab now pass the Brain gate status and DOM availability as allowlisted, read-only values. No web order endpoint was introduced.
6. Closed-bar age protection before demo submission (local maximum 60–900 s after bar close). Existing account isolation, hard-denied Grok demo login, broker-native lot sizing, SL/TP, daily loss limit and order idempotency remain.

## Developer-run checks

Python mocks (run from the parent folder of `sentinel_trader`):

```bash
python -m unittest discover -s sentinel_trader/tests -p 'test_*.py' -v
```

JS contract:

```bash
node --test sentinel-bridge/tests/trader-status.test.cjs
```

GitHub Actions tests are necessary but **do not prove** Windows MT5 broker connectivity, order-book availability, profitability, or live fill reconciliation.

## Windows setup later, after review and **only on an independent DEMO**

- Use a **separate** MT5 terminal and DEMO login; do not attach this engine to the active Grok terminal. Configure `allowed_login` and `allowed_server` locally. No passwords are put in this repository or online console.
- Start with `mode=research`, `strategy_policy=verified_only`, `orderbook_mode=observe`. Collect actual DOM diagnostics, research decisions and a proper broker-history dataset. The account and server must be correct for startup.
- To test an **unvalidated trial on DEMO**, an operator must explicitly choose `strategy_policy=demo_trial`, set both `SENTINEL_ENABLE_DEMO_TRADING=YES_I_AUTHORIZE_SENTINEL_DEMO_ONLY` and `SENTINEL_UNVERIFIED_DEMO_TRIAL=YES_UNVERIFIED_SENTINEL_DEMO_TRIAL` **locally**, and pass separate demo identity. No automatic remote activation exists; current deployment and runtime remain disabled.
- `orderbook_mode=confirm` is usable only when the broker publishes DOM, with a real sequence of fresh observations. Missing DOM correctly blocks the entry.
- The authenticated status upload is optional and requires the Sentinel Windows paired agent and a separately provisioned Neon status table; it cannot trade through the website.

## Work remaining before actual DEMO validation

| Priority | Missing | Why |
|---|---|---|
| P0 | Independent MT5 DEMO instance and local Windows runtime | Cannot broker-test without separate endpoint; archived bot remains untouched |
| P0 | Genuine XAUUSD/NAS100 deep history, MT5 symbol specs, observed broker costs | Existing historical feed timeouts and missing historical spread mean candidate quality is unproven |
| P0 | Real broker order/deal/position reconciliation, slippage and trade attribution | Mock success is not actual fill evidence |
| P1 | Online forwarding of local research outcomes to central Sentinel intelligence | This release records local decision provenance, not an always-learning remote executor |
| P1 | Exchange-grade depth/trade stream (BTC exchange, GC futures), sequence/gap handling and timestamps | Broker DOM is a partial, venue-specific view and may be empty |
| P1 | Walk-forward, multiple-testing correction and robust forward shadow/demo experiment registry | Two baseline strategies are not verified profitable |
| P2 | Observability, alerts and controlled rollout | Infrastructure cannot claim 24/7 running until Windows service and cloud are verified |

**Scope boundary:** Source code written, tests run, nothing published or traded. An approved-looking JSON file is not independently proof that real trades occurred.
