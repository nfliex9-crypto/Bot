"""Independent WEEX USDT Perpetual read-only observation service.

Uses native CCXT Pro WebSocket subscriptions and existing vetted validation.
Only locally persists a minimal live dashboard status snapshot. It does not
create a broker account, submit orders, or import any MT5 code/config.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from weex_futures_feed import PAIRS, FutureEvidence, verify_swap

STATE_FILE = ROOT / "data" / "market_status.json"


def snapshot(evidence: dict[str, FutureEvidence], now: float) -> dict:
    result = {"venue": "WEEX", "market_type": "USDT_LINEAR_PERPETUAL",
              "source": "CCXT_PRO_WEEX_PUBLIC_FUTURES",
              "orders_enabled": False, "received_at_ms": int(now * 1000),
              "markets": {}}
    for symbol, ev in evidence.items():
        is_fresh = (
            ev.invalid == 0 and ev.unique_trades > 0 and ev.book_updates > 0
            and 0 <= now - ev.latest_book_receipt <= 12
            and 0 <= now - ev.latest_trade_receipt <= 12
            and 0 < ev.last_bid < ev.last_ask
            and ev.last_trade > 0
        )
        if not is_fresh:
            continue
        stamp = min(ev.latest_book_receipt, ev.latest_trade_receipt)
        result["markets"][symbol] = {
            "bid": ev.last_bid, "ask": ev.last_ask, "last": ev.last_trade,
            "received_ms": int(stamp * 1000),
            "trades_seen": ev.unique_trades,
            "verified_source": "CCXT_PRO_WEEX_PUBLIC_FUTURES",
        }
    return result


def write_atomic(dest: Path, payload: dict):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".new")
    part.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(part, dest)


async def watch_one(symbol: str, evidence: dict, exchange):
    ev = evidence[symbol]

    async def books():
        while True:
            book = await asyncio.wait_for(exchange.watch_order_book(symbol, 15), 20)
            ev.book(book, time.time())

    async def trades():
        while True:
            tape = await asyncio.wait_for(exchange.watch_trades(symbol), 20)
            ev.trades(tape, time.time())
            # Bound the status-only trade-ID set for long-running local observers.
            # Counter is observational, NOT used for accounting or fills.
            if len(ev.seen_trade_ids) > 30000:
                ev.seen_trade_ids.clear()
                ev.unique_trades = 0
    await asyncio.gather(books(), trades())


async def run(symbols: tuple[str, ...], dest: Path, seconds: int | None):
    import ccxt.pro
    start = time.monotonic()
    retry = 0
    while seconds is None or time.monotonic() - start < seconds:
        evidence = {s: FutureEvidence(s) for s in symbols}
        exchange = ccxt.pro.weex({
            "enableRateLimit": True,
            "options": {"defaultType": "swap", "newUpdates": True},
        })
        tasks = []
        try:
            await asyncio.wait_for(exchange.load_markets(), timeout=30)
            for symbol in symbols:
                verify_swap(exchange.market(symbol), symbol)
                tasks.append(asyncio.create_task(watch_one(symbol, evidence, exchange)))
            retry = 0
            while seconds is None or time.monotonic() - start < seconds:
                await asyncio.sleep(2)
                for task in tasks:
                    if task.done():
                        task.result()  # propagate upstream disconnect / stale feed
                data = snapshot(evidence, time.time())
                write_atomic(dest, data)
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as exc:
            retry += 1
            write_atomic(dest, snapshot({}, time.time()))
            print(f"WEEX collector read-only reconnect required: {type(exc).__name__}", flush=True)
            await asyncio.sleep(min(30, 2 ** min(retry, 5)))
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await exchange.close()
    write_atomic(dest, snapshot({}, time.time()))


def main():
    p = argparse.ArgumentParser(description="Independent real WEEX Perpetual public data observer, no orders")
    p.add_argument("--symbols", nargs="+", choices=PAIRS, default=list(PAIRS))
    p.add_argument("--seconds", type=int, default=None)
    p.add_argument("--out", type=Path, default=STATE_FILE)
    args = p.parse_args()
    if args.seconds is not None and not 30 <= args.seconds <= 86400:
        p.error("Duration must be 30-86400 seconds")
    asyncio.run(run(tuple(args.symbols), args.out, args.seconds))


if __name__ == "__main__":
    main()
