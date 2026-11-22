# Sentinel Crypto — Futures Demo engineering acceptance (22 November 2026)

**Scope:** WEEX BTC/ETH/SOL USDT perpetual futures; public market-data research, Arrow Parquet capture, safe order construction preview, no production private account, no demo order sent. **Branch:** `sentinel-crypto-orderflow-v1`. **PR:** https://github.com/nfliex9-crypto/Bot/pull/10 (DRAFT, unmerged).

## Latest all-green functional pipeline

**Verified GitHub Actions (seven independent jobs):** https://github.com/nfliex9-crypto/Bot/actions/runs/45073512314

1. **55 Python tests: PASS** on GitHub Python 3.13, with pinned upstream `ccxt==4.5.93` and `pyarrow==21.0.0`. Scenarios cover wrong market type, wrong venue contract, missing order-book levels, crossed levels, stale timestamps, missing trade ID, duplicate trades, Parquet round trip, tampered SHA256, wrong instrument/market, and private REST request host restrictions.
2. **Real public futures WEEX WebSocket PASS:** BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT all delivered genuine L2 order book and executed trade tape. Upstream CCXT Pro maintains the order book. This is not Spot and no fabricated market data is inserted.
3. **Real WEEX BTC Futures Parquet PASS:** latest validated Arrow artifact includes **80 merged book snapshots + 221 unique executed trades = 301 rows**, all attributed to WEEX BTC/USDT:USDT and validated with venue timestamps, deterministic schema, Parquet readback, manifest/hash checks. Captured in one short read-only session; not a week of history.
4. **Futures reference PASS:** last executed contract trade **60,978.8**, Mark **60,970.0**, Index **61,001.226388889**, last funding rate **-0.00000952**, forecast funding **0.00003777**, open interest **153,812.2216 contract units**. These values are dated **2026-11-22 at around 21:43 UTC**, not ongoing live prices. Origin is public WEEX contract data; futures Last is sourced from actual recent executed trades.
5. **CCXT BUY/SELL demo request construction PASS:** public futures market min quantity (CCXT-unified) **0.0001** and public depth were used for a native order request preview; signing target `api-sim.weex.com` and **zero private order requests**. These are previews only — not real API-accepted simulation orders, IDs or executions.
6. **No demo account connection claimed:** running `weex_demo_account.py` with credentials absent intentionally returns `DEMO_ACCOUNT_NOT_CONNECTED`. No WEEX simulated balance, positions, orders or PnL are known.

## Failure identified and truly fixed

The first public futures reference test properly failed closed because `fetch_ticker()` gave an approximately **600,937 millisecond old** 24-hour ticker timestamp, which is not valid as a fresh last-executed trade. We **did not** widen the staleness allowance or use Mark as an invented Last. The revised source is CCXT's official `fetch_trades(symbol, limit=10)`, where the latest actual exchange-stamped executed futures contract trade determines Last. The distinct Mark, Index, last/forecast Funding and OI values use their respective public Futures endpoints. The revised live job passed.

## Security and limitations

- All WEEX private API URL paths are constrained by `weex_demo_guard.py` to `https://api-sim.weex.com/capi/v3/`; Spot private API, production URLs and WEEX old sandbox path are rejected. No live-money order route enabled.
- Upstream CCXT Pro WEEX `handle_order_book` reconstructs the book but its public Python handler should **not be assumed to guarantee perfect U/u sequence continuity** after packet loss. Current snapshots preserve the upstream `nonce` and exchange timestamp. Additional connection-reset and sequence-gap verification remains required for 24/7 order-flow research; SHA256 proves integrity of the stored file, not completeness of the exchange feed.
- Parquet session captures are limited samples. GitHub's downloadable artifacts expire in **7 days**; no persistent 24/7 storage volume, unattended service or dashboard has been deployed.
- No authenticated WEEX simulation API has been used (missing separate demo credentials); order preview is **not execution** and no strategy profitability has been shown.
- No WEEX Futures historical OOS evaluation, fee/funding/slippage-inclusive audited performance, or leveraged demo position reconciliation has occurred.
- Existing MT5 trading system, existing cloud services, Vercel, Neon, Railway and production branches were **not edited**. GitHub compare against `sentinel-adaptive-intelligence-v2` showed **zero files changed outside `crypto/` and `.github/workflows/crypto-*`**.

## Next controlled gates

1. Configure user-owned **WEEX SIM** API key, secret and passphrase exclusively in an independent crypto service; verify actual simulated balance and region eligibility. No credential value should ever be copied into a GitHub file, test log or chat.
2. Validate real simulation order response/acceptance, reduce-only or hedge position semantics, order IDs, cancellations, position/fill reconciliation and liquidation/Mark behavior on `api-sim.weex.com`, using bounded short-lived test orders.
3. Persist futures L2/tape/Mark/Index/Funding/OI with service-volume rotation, resource bounds, transport reconnection and continuity monitoring.
4. Only after sufficient weeks of native WEEX Perpetual data, run independent out-of-sample futures-specific tests and supervised **demo** forward trading. No funded orders without separate approval.
