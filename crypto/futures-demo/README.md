# Sentinel Crypto FUTURES DEMO — WEEX (November 2026)

**User-selected product: USDT perpetual FUTURES, NOT SPOT.** The previous Kraken Spot PCAP/Parquet research is archived historical proof only, **not suitable** for modelling WEEX BTCUSDT perpetual execution. Existing MT5 system is isolated and untouched.

## Upstream components

- **[CCXT Pro 4.5.93](https://github.com/ccxt/ccxt/tree/master/python/ccxt/pro)** — upstream WEEX official adapter, public Futures WebSocket Order Book and real executed trade tape. Our code only checks attribution/quality, no home-built market-data gateway.
- **[WEEX official Futures API](https://www.weex.com/api-doc/products/futures/QuickStart/GeneralInformation)** — simulation REST domain `https://api-sim.weex.com`, normal `/capi/v3/` paths, official SDK/CCXT request signing. Public futures market data remains the real market.
- **NautilusTrader** — retained research/backtesting engine; its native Kraken Spot Parquet records **must not** be mislabelled as WEEX Futures order flow or fills. A WEEX-specific validated futures historical data importer/adapter is still pending.

## Critical CCXT compatibility finding (2026-11-22)

Current CCXT `weex.set_sandbox_mode(True)` (4.5.93) still routes demo via now-deprecated `/capi/v3/sim/` endpoints on **production host**. WEEX's updated API uses **simulation domain** `api-sim.weex.com` with the regular `/capi/v3/` routes. We have therefore deliberately **not** used CCXT's built-in sandbox flag; instead we subclass only its request signing boundary to permit future PRIVATE endpoints **only** on `api-sim.weex.com`. Any spot private path, production private URL or deprecated sim path aborts. Signatures/order API remain the external CCXT code. This boundary has no keys or orders of its own.

## Proven public Futures feed (real exchange, no keys)

```bash
python3.13 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r crypto/futures-demo/requirements.txt
python crypto/futures-demo/weex_futures_feed.py --symbol 'BTC/USDT:USDT' --seconds 40
```

The script accepts only BTC/ETH/SOL USDT-settled **linear perpetual** contracts. It rejects SPOT/inactive/wrong markets and fails if the public genuine CCXT Pro WebSocket does not yield a noncrossed book and unique executed trades. Its report distinguishes missing exchange timestamps from local reception; it never fills gaps with invented prices.

## Official WEEX Futures simulated-account connection

To authenticate an actual **exchange-owned demo account**, create appropriate simulation API credentials under the permitted WEEX account. Store them in the intended **separate crypto environment**, not GitHub source, not MT5, and never inside chat.

```bash
export WEEX_SIM_API_KEY='...'
export WEEX_SIM_API_SECRET='...'
export WEEX_SIM_API_PASSPHRASE='...'
python crypto/futures-demo/weex_demo_account.py
```

This script is **read-only**: it verifies that WEEX's simulation service accepts an account/balance request and returns only an authenticated/not-authenticated status; it never submits trades. If no keys are configured, it reports `DEMO_ACCOUNT_NOT_CONNECTED` and exits nonzero.

**Automatic demo entry/exit NOT active yet.** Before activation: verify simulation account reachability, official order/position API compatibility, exchange precision, hedge vs one-way mode, position reconciliation, trade ID idempotency, liquidation/mark price, and EU product eligibility. Only simulation host may accept private operations; cannot turn this component into real trading by switching a flag.

## Futures vs Spot prices

A perpetual last-traded contract price differs from Spot; `Mark Price` and `Index Price` can also differ. Funding changes net PnL without changing the book's printed last price. Data and backtests must preserve **WEEX futures venue/product/symbol**, collateral and funding rates rather than substituting Kraken Spot or another exchange's market.

## Current acceptance

- CCXT WEEX 4.5.93 official market integration selected; real Futures GitHub CI connection must pass before labelling it proven.
- Offline tests: product guards, bad book/trades, signing URLs; GitHub CI provides independent verification.
- User-supplied exchange simulation keys are not present in this repo. Thus **no authenticated demo orders have been placed**, and it is wrong to claim bot has traded.
- Live MT5 and services untouched, no Vercel/Railway deploy, no production merge. Draft PR #10 only.
