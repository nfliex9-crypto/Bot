"""Read-only WEEX USDT perpetual futures source witness via upstream CCXT Pro.
NO spot order book, synthetic ticks, account auth, or order execution.
"""
from __future__ import annotations
import argparse
import asyncio
import json
import math
import time
from dataclasses import dataclass, field

PAIRS = ("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT")


def positive(x):
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(v) and v > 0


def verify_swap(market: dict, requested: str):
    if (market.get("symbol") != requested or not market.get("swap")
        or not market.get("contract") or market.get("spot")
        or market.get("settle") != "USDT" or market.get("linear") is not True):
        raise ValueError("NOT_WEEX_USDT_LINEAR_PERPETUAL")
    if market.get("active") is False:
        raise ValueError("INACTIVE_PERPETUAL_MARKET")
    return True


@dataclass
class FutureEvidence:
    symbol: str
    book_updates: int = 0
    unique_trades: int = 0
    invalid: int = 0
    latest_book_receipt: float = 0
    latest_trade_receipt: float = 0
    last_bid: float = 0
    last_ask: float = 0
    last_trade: float = 0
    trade_ids: set = field(default_factory=set)
    book_nonce: object = None
    missing_exchange_timestamp: int = 0

    def book(self, entry: dict, now: float):
        try:
            bid, bqty = entry["bids"][0][:2]
            ask, aqty = entry["asks"][0][:2]
            if not all(map(positive, (bid, bqty, ask, aqty))) or float(bid) >= float(ask):
                raise ValueError("CROSSED_BOOK")
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            self.invalid += 1
            return
        stamp = entry.get("timestamp")
        if stamp is None:
            self.missing_exchange_timestamp += 1
        elif not positive(stamp) or abs(now - stamp / 1000) > 30:
            self.invalid += 1
            return
        self.book_updates += 1
        self.last_bid = float(bid)
        self.last_ask = float(ask)
        self.book_nonce = entry.get("nonce")
        self.latest_book_receipt = now

    def trades(self, entries, now: float):
        for item in entries:
            try:
                if item.get("symbol") != self.symbol or item.get("side") not in ("buy", "sell"):
                    raise ValueError("WRONG_SYMBOL_OR_SIDE")
                if not positive(item.get("price")) or not positive(item.get("amount")):
                    raise ValueError("INVALID_EXECUTED_TRADE")
                ts = item.get("timestamp")
                if ts is None:
                    self.missing_exchange_timestamp += 1
                elif not positive(ts) or abs(now - ts / 1000) > 30:
                    raise ValueError("STALE_TRADE_TAPE")
                ident = item.get("id")
                if ident is None:
                    # No unique venue trade ID, so do not claim a distinct trade.
                    continue
                if ident in self.trade_ids:
                    continue
                self.trade_ids.add(ident)
                self.unique_trades += 1
                self.last_trade = float(item["price"])
                self.latest_trade_receipt = now
            except (ValueError, TypeError, OverflowError, KeyError):
                self.invalid += 1

    def report(self, now: float, duration: int):
        fresh = (
            self.latest_trade_receipt > 0 and self.latest_book_receipt > 0
            and 0 <= now - self.latest_trade_receipt <= min(15, duration)
            and 0 <= now - self.latest_book_receipt <= min(15, duration)
        )
        ok = bool(
            self.book_updates > 0 and self.unique_trades > 0 and not self.invalid
            and self.last_bid < self.last_ask and fresh
        )
        return {
            "status": "LIVE_WEEX_PERP_FEED_VERIFIED" if ok else "DATA_UNVERIFIED",
            "venue": "WEEX", "market": "USDT_LINEAR_PERPETUAL", "symbol": self.symbol,
            "origin": "ccxt_pro_weex_public_futures_websocket",
            "book_update_callbacks": self.book_updates,
            "unique_executed_trades": self.unique_trades,
            "invalid_events": self.invalid,
            "missing_exchange_timestamp": self.missing_exchange_timestamp,
            "best_bid": self.last_bid if self.book_updates else None,
            "best_ask": self.last_ask if self.book_updates else None,
            "last_futures_trade": self.last_trade if self.unique_trades else None,
            "spot_prices_used": False, "orders_enabled": False,
            "synthetic_market_data": False, "demo_account_authenticated": False,
        }


async def witness(symbol: str, seconds: int):
    import ccxt.pro
    exchange = ccxt.pro.weex({
        "enableRateLimit": True,
        "options": {"defaultType": "swap", "newUpdates": True}
    })
    ev = FutureEvidence(symbol)
    try:
        await exchange.load_markets()
        verify_swap(exchange.market(symbol), symbol)
        start = time.monotonic()

        async def books():
            while time.monotonic() - start < seconds:
                entry = await asyncio.wait_for(exchange.watch_order_book(symbol, 15), timeout=15)
                ev.book(entry, time.time())

        async def trades():
            while time.monotonic() - start < seconds:
                entries = await asyncio.wait_for(exchange.watch_trades(symbol), timeout=15)
                ev.trades(entries, time.time())

        await asyncio.gather(books(), trades())
        return ev.report(time.time(), seconds)
    finally:
        await exchange.close()


def main():
    parser = argparse.ArgumentParser(description="Public WEEX Perpetual L2 + tape, read-only")
    parser.add_argument("--symbol", default="BTC/USDT:USDT", choices=PAIRS)
    parser.add_argument("--seconds", type=int, default=40)
    args = parser.parse_args()
    if not 20 <= args.seconds <= 300:
        parser.error("seconds must be between 20 and 300")
    try:
        result = asyncio.run(witness(args.symbol, args.seconds))
    except Exception as exc:
        result = {
            "status": "DATA_UNVERIFIED", "error_type": type(exc).__name__,
            "error_detail": str(exc)[:250], "venue": "WEEX", "symbol": args.symbol,
            "market": "USDT_LINEAR_PERPETUAL", "orders_enabled": False,
            "synthetic_market_data": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "LIVE_WEEX_PERP_FEED_VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
