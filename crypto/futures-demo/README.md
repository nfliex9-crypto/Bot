# Sentinel Crypto — WEEX USDT Perpetual Futures DEMO

**Product:** WEEX USDT-settled perpetual futures, NOT Spot. Isolated GitHub research branch `sentinel-crypto-orderflow-v1`, Draft PR #10. **MT5 production, deployment and account permissions unchanged**.

## External upstream libraries / verified market data

- `ccxt==4.5.93` including CCXT Pro's WEEX public Futures WebSocket, official market metadata and order-request formatting.
- `pyarrow==21.0.0` native Parquet writing/reading with ZSTD compression. WEEX market depth is merged by **CCXT Pro**, not home-built.
- WEEX official simulation REST host **`https://api-sim.weex.com`**, identical normal Futures API paths to production but separate destination; the upstream CCXT's old sandbox path is not used.
- Spot Kraken historical artifacts stay archived and **are not eligible** as training data, entry prices, fills or order flow for WEEX futures.

### Verified on real public WEEX Futures (2026-11-22)

**CI:** [WEEX crypto futures pipeline](../../.github/workflows/crypto-weex-futures-demo.yml).

1. **BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT**: Public WEEX actual futures L2 book and executed-trade feed succeeded. Every symbol is checked against the *exchange's* `market.contract`, `swap`, `linear`, `settle`, and `spot` flags before starting. Missing/crossed/old data fails instead of fabricating prices.
2. **Native Arrow futures archive:** `weex_futures_parquet.py` uses CCXT Pro and Arrow to store **real** per-contract merged full top-N book snapshots AND individual executed trade events. Source, venue, pair, exchange timestamp, received timestamp, trade IDs, sequence, book levels and side are present. Parquet + manifest SHA-256 verified by independent readback and full row count. This is **not yet** a proof that any dropped WebSocket sequence is perfectly recoverable.
3. **Futures prices distinguished:** WEEX `fetch_ticker()` had a 24-hour ticker timestamp approximately **10 minutes stale** during real tests, so that source was **rejected**, not relaxed. `weex_futures_reference.py` now takes the **Last Price from current actual executed Futures trades**, while `Mark`, `Index`, `lastFundingRate`, `forecastFundingRate`, and `Open Interest` come from CCXT's authenticated-free WEEX **public Futures REST**. All their source timestamps are validated. Negative funding is supported.
4. **Native CCXT buy/sell preview** `weex_demo_order_preview.py`: reads real futures public market precision and best bid/ask, builds a CCXT contract LIMIT BUY and SELL request, and checks that their **signed** URLs point only to simulation. **No private order request is sent** and no order id/fill is fabricated.
5. **Fail-closed test suite:** 55 tests passed as of 2026-11-22, including market/source rejection, bad bids/asks, SHA-256 corruption, time staleness, duplicate trades, signed simulation destination, and no-order preview.

### Safe commands

```bash
python3.13 -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\Activate.ps1
python -m pip install -r crypto/futures-demo/requirements.txt
python -m unittest discover -s crypto/futures-demo -p 'test_*.py' -v
# Real WEEX Futures data, read-only:
python crypto/futures-demo/weex_futures_feed.py --symbol 'BTC/USDT:USDT' --seconds 40
python crypto/futures-demo/weex_futures_reference.py --symbol 'BTC/USDT:USDT'
python crypto/futures-demo/weex_futures_parquet.py --symbol 'BTC/USDT:USDT' --seconds 40 --out-dir /path/to/separate/persistent/crypto-captures
# Native CCXT order template but NO order is transmitted:
python crypto/futures-demo/weex_demo_order_preview.py --symbol 'BTC/USDT:USDT' --side buy
python crypto/futures-demo/weex_demo_order_preview.py --symbol 'BTC/USDT:USDT' --side sell
```

Do not put any private API secrets in commands, chat messages, screenshots or GitHub files. Save capture files to an actual **persistent** storage volume on an independent crypto service when deployed; GitHub Actions stores CI artifacts **temporarily for 7 days** and cannot serve as a 24/7 runtime.

## Account readiness — no demo orders yet

`weex_demo_guard.py` subclasses CCXT only at the **signing destination boundary**: all private Futures API requests are restricted to `api-sim.weex.com`. Spot private requests, production Futures private URL and obsolete `/capi/v3/sim/` endpoints are blocked. This guard is proven against real CCXT 4.5.93 by no-network tests.

WEEX account *authentication* was **not** validated because this independent crypto environment does not have the user's **demo-only** key, secret, passphrase. This means **NO active demo trades, positions, fills, equity or PnL can be claimed.**

Only once an eligible user has securely configured the three demo-only secrets in a separate crypto service:

```text
WEEX_SIM_API_KEY
WEEX_SIM_API_SECRET
WEEX_SIM_API_PASSPHRASE
```

...can the existing **read-only** `weex_demo_account.py` validate that the official simulated account/balance endpoint is reachable. No write actions are part of that probe.

**Next execution gate:** investigate and test official demo order response, order idempotency, position mode and reconciliation, min quantity, margin, liquidation/mark price and stop-loss behavior on the simulation host. Never enable production trading or reuse MT5 keys. Verify regional futures-product eligibility for Belgium before any funded account use.

## Truthful acceptance boundary

- Proven: Public WEEX Futures read-only streaming, per-contract reference quotes, Arrow storage/verification, signed *request previews* to simulation, offline regression tests.
- Not proven: 24/7 persistence, perfect WebSocket gap recovery, actual authenticated WEEX Demo orders/fills, profitable strategy, WEEX futures-specific out-of-sample backtest, execution slippage/funding reconciliation, continuous monitor and live dashboard.
- The prior NautilusTrader Kraken Spot technical backtest **does not test WEEX Futures**; never extrapolate it.
- Draft branch only; no merge/deploy and no changes to MT5.
