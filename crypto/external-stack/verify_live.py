"""External-only live data witness. No book rebuilding, strategy, synthetic data, or orders.

Uses the official Cryptofeed trade and L2 callbacks. Fails closed if either
stream is missing, inconsistent or stale. Always scoped to one venue/pair.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import dataclass


@dataclass
class Evidence:
    venue: str
    symbol: str
    trades: int = 0
    books: int = 0
    latest_trade_receipt: float = 0.0
    latest_book_receipt: float = 0.0
    latest_bid: float = 0.0
    latest_ask: float = 0.0
    invalid_events: int = 0

    def summary(self, now: float | None = None, max_age: float = 15.0) -> dict:
        now = time.time() if now is None else now
        fresh = (
            self.latest_trade_receipt > 0
            and self.latest_book_receipt > 0
            and 0 <= now - self.latest_trade_receipt <= max_age
            and 0 <= now - self.latest_book_receipt <= max_age
        )
        valid_book = 0 < self.latest_bid < self.latest_ask
        passed = bool(self.trades > 0 and self.books > 0 and fresh and valid_book and not self.invalid_events)
        return {
            "status": "VERIFIED_RECENT_EXTERNAL_EVENTS" if passed else "DATA_UNVERIFIED",
            "source": "cryptofeed",
            "venue": self.venue,
            "symbol": self.symbol,
            "market_type": "SPOT_RESEARCH",
            "order_book_callbacks": self.books,
            "executed_trade_callbacks": self.trades,
            "invalid_events": self.invalid_events,
            "bid": self.latest_bid if valid_book else None,
            "ask": self.latest_ask if valid_book else None,
            "last_trade_age_seconds": round(now - self.latest_trade_receipt, 2) if self.latest_trade_receipt else None,
            "last_book_age_seconds": round(now - self.latest_book_receipt, 2) if self.latest_book_receipt else None,
            "orders_enabled": False,
            "synthetic_market_data": False,
        }


def valid_number(value) -> bool:
    try:
        number = float(value)
        return math.isfinite(number) and number > 0
    except (ValueError, TypeError, OverflowError):
        return False


async def witness(venue: str, symbol: str, seconds: float) -> dict:
    # Lazy import keeps the strict validation tests runnable without third-party packages.
    from cryptofeed import FeedHandler
    from cryptofeed.defines import L2_BOOK, TRADES

    evidence = Evidence(venue, symbol)

    async def on_trade(event, received: float):
        if event.exchange != venue or event.symbol != symbol:
            evidence.invalid_events += 1
            return
        if not valid_number(event.price) or not valid_number(event.amount):
            evidence.invalid_events += 1
            return
        if str(event.side).lower() not in ("buy", "sell"):
            evidence.invalid_events += 1
            return
        evidence.trades += 1
        evidence.latest_trade_receipt = received

    async def on_book(event, received: float):
        if event.exchange != venue or event.symbol != symbol:
            evidence.invalid_events += 1
            return
        if not event.book.bids or not event.book.asks:
            evidence.invalid_events += 1
            return
        bid, _bid_qty = event.book.bids.index(0)
        ask, _ask_qty = event.book.asks.index(0)
        if not valid_number(bid) or not valid_number(ask) or not valid_number(_bid_qty) or not valid_number(_ask_qty) or float(bid) >= float(ask):
            evidence.invalid_events += 1
            return
        evidence.books += 1
        evidence.latest_book_receipt = received
        evidence.latest_bid = float(bid)
        evidence.latest_ask = float(ask)

    feed = FeedHandler(on_feed_error="remove_feed")
    feed.add_feed(
        venue,
        symbols=[symbol],
        channels=[TRADES, L2_BOOK],
        callbacks={TRADES: on_trade, L2_BOOK: on_book},
    )

    async def finish():
        await asyncio.sleep(seconds)
        feed.request_stop()

    stopper = asyncio.create_task(finish())
    try:
        await feed.run_async()
    finally:
        stopper.cancel()
    return evidence.summary()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify LIVE external Kraken/Binance spot book+trades")
    parser.add_argument("--exchange", default="KRAKEN", choices=("KRAKEN", "BINANCE"))
    parser.add_argument("--symbol", default="BTC-USD")
    parser.add_argument("--seconds", type=float, default=45)
    args = parser.parse_args()

    if not 15 <= args.seconds <= 300:
        parser.error("--seconds must be between 15 and 300")
    if args.exchange == "KRAKEN" and args.symbol not in ("BTC-USD", "ETH-USD", "SOL-USD"):
        parser.error("Kraken spot witness supports BTC-USD, ETH-USD, SOL-USD")
    if args.exchange == "BINANCE" and args.symbol not in ("BTC-USDT", "ETH-USDT", "SOL-USDT"):
        parser.error("Binance spot witness supports BTC-USDT, ETH-USDT, SOL-USDT")

    try:
        result = asyncio.run(witness(args.exchange, args.symbol, args.seconds))
    except Exception as exc:
        result = {
            "status": "DATA_UNVERIFIED",
            "source": "cryptofeed",
            "venue": args.exchange,
            "symbol": args.symbol,
            "error_type": type(exc).__name__,
            "orders_enabled": False,
            "synthetic_market_data": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "VERIFIED_RECENT_EXTERNAL_EVENTS" else 1


if __name__ == "__main__":
    sys.exit(main())
