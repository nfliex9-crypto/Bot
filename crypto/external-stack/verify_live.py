"""Read-only live exchange feed verification via upstream Cryptofeed 3.0.5.

Does NOT implement a venue protocol, order book, strategy, or synthetic data.
A successful check proves one venue/pair delivered fresh book and trade callbacks
in the current invocation, NOT that the venue or bot will stay live indefinitely.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import dataclass

SUPPORTED = {
    "KRAKEN": frozenset(("BTC-USD", "ETH-USD", "SOL-USD")),
    "BINANCE": frozenset(("BTC-USDT", "ETH-USDT", "SOL-USDT")),
}


def positive_number(value: object) -> bool:
    try:
        v = float(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(v) and v > 0


def acceptable_time(event_time: object, received: object, now: float, max_delay: float = 30.0) -> bool:
    """Require exchange event time <= receipt time <= now, with small clock tolerance.

    The non-monotonic seconds here are wall-clock instants from Cryptofeed,
    not local monotonic timers. Kraken supplies event timestamps for both streams.
    """
    try:
        evt = float(event_time)
        rcv = float(received)
    except (TypeError, ValueError, OverflowError):
        return False
    return (math.isfinite(evt) and math.isfinite(rcv)
            and 0 < evt <= rcv + 2.0 and rcv <= now + 2.0
            and now - evt <= max_delay and now - rcv <= max_delay
            and evt <= now + 2.0)


@dataclass
class Evidence:
    venue: str
    symbol: str
    trades: int = 0
    books: int = 0
    latest_trade_receipt: float = 0.0
    latest_book_receipt: float = 0.0
    latest_trade_event: float = 0.0
    latest_book_event: float = 0.0
    latest_bid: float = 0.0
    latest_ask: float = 0.0
    invalid_events: int = 0

    def observe_trade(self, trade: object, received: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if (getattr(trade, "exchange", None) != self.venue or
            getattr(trade, "symbol", None) != self.symbol or
            str(getattr(trade, "side", "")).lower() not in ("buy", "sell") or
            not positive_number(getattr(trade, "price", None)) or
            not positive_number(getattr(trade, "amount", None)) or
            not acceptable_time(getattr(trade, "timestamp", None), received, now)):
            self.invalid_events += 1
            return
        self.trades += 1
        self.latest_trade_receipt = float(received)
        self.latest_trade_event = float(trade.timestamp)

    def observe_book(self, book: object, received: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if (getattr(book, "exchange", None) != self.venue or
            getattr(book, "symbol", None) != self.symbol or
            not acceptable_time(getattr(book, "timestamp", None), received, now)):
            self.invalid_events += 1
            return
        try:
            ladder = book.book  # Cryptofeed's upstream managed OrderBook
            if not ladder.bids or not ladder.asks:
                raise ValueError("EMPTY_BOOK")
            bid, bid_qty = ladder.bids.index(0)
            ask, ask_qty = ladder.asks.index(0)
            if (not all(positive_number(x) for x in (bid, ask, bid_qty, ask_qty))
                or float(bid) >= float(ask)):
                raise ValueError("CROSSED_OR_INVALID_BOOK")
        except (AttributeError, IndexError, TypeError, ValueError, OverflowError):
            self.invalid_events += 1
            return
        self.books += 1
        self.latest_book_receipt = float(received)
        self.latest_book_event = float(book.timestamp)
        self.latest_bid = float(bid)
        self.latest_ask = float(ask)

    def summary(self, now: float | None = None, max_age: float = 15.0) -> dict:
        now = time.time() if now is None else now
        fresh = all(
            0 < timestamp <= now + 2.0 and 0 <= now - timestamp <= max_age
            for timestamp in (self.latest_trade_receipt, self.latest_book_receipt,
                              self.latest_trade_event, self.latest_book_event)
        )
        valid_book = 0 < self.latest_bid < self.latest_ask
        passed = bool(self.trades and self.books and fresh and valid_book and not self.invalid_events)
        return {
            "status": "VERIFIED_RECENT_EXTERNAL_EVENTS" if passed else "DATA_UNVERIFIED",
            "source": "cryptofeed_3.0.5",
            "venue": self.venue,
            "symbol": self.symbol,
            "market_type": "SPOT_PUBLIC_ONLY",
            "order_book_callbacks": self.books,
            "executed_trade_callbacks": self.trades,
            "invalid_events": self.invalid_events,
            "best_bid": self.latest_bid if valid_book else None,
            "best_ask": self.latest_ask if valid_book else None,
            "last_trade_age_seconds": round(now - self.latest_trade_event, 2) if self.latest_trade_event else None,
            "last_book_age_seconds": round(now - self.latest_book_event, 2) if self.latest_book_event else None,
            "orders_enabled": False,
            "synthetic_market_data": False,
        }


async def witness(venue: str, symbol: str, seconds: float) -> dict:
    from cryptofeed import FeedHandler
    from cryptofeed.defines import L2_BOOK, TRADES

    evidence = Evidence(venue, symbol)

    async def trade_callback(event, received):
        evidence.observe_trade(event, received)

    async def book_callback(event, received):
        evidence.observe_book(event, received)

    # Kraken's adapter has checksum validation on by default; never turn it off.
    # max_depth=10 limits network/CPU requirements and still validates its top levels.
    handler = FeedHandler(on_feed_error="raise")
    handler.add_feed(
        venue, symbols=[symbol], channels=[TRADES, L2_BOOK], max_depth=10,
        callbacks={TRADES: trade_callback, L2_BOOK: book_callback},
    )

    async def stop_after_window():
        await asyncio.sleep(seconds)
        handler.request_stop()

    stopper = asyncio.create_task(stop_after_window())
    try:
        await asyncio.wait_for(handler.run_async(), timeout=seconds + 30.0)
    finally:
        stopper.cancel()
    return evidence.summary()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public real L2 and executed trades")
    parser.add_argument("--exchange", default="KRAKEN", choices=sorted(SUPPORTED))
    parser.add_argument("--symbol", default="BTC-USD")
    parser.add_argument("--seconds", type=float, default=60.0)
    args = parser.parse_args()
    if args.symbol not in SUPPORTED[args.exchange]:
        parser.error(f"Invalid {args.exchange} spot pair: {args.symbol}")
    if not 30.0 <= args.seconds <= 300.0:
        parser.error("Duration must be between 30 and 300 seconds")

    try:
        result = asyncio.run(witness(args.exchange, args.symbol, args.seconds))
    except Exception as exc:
        result = {"status": "DATA_UNVERIFIED", "source": "cryptofeed_3.0.5",
                  "venue": args.exchange, "symbol": args.symbol,
                  "error_type": type(exc).__name__,
                  "orders_enabled": False, "synthetic_market_data": False}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "VERIFIED_RECENT_EXTERNAL_EVENTS" else 1


if __name__ == "__main__":
    sys.exit(main())
