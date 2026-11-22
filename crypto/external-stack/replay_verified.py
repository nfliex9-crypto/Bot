"""Fail-closed replay of REAL Cryptofeed PCAP using Cryptofeed's own playback API.

NO synthetic prices, own order book implementation, network trading, or
cross-venue merging. Results here validate source replay only, not strategy edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from verify_live import acceptable_time, positive_number


class CaptureRejected(ValueError):
    """Capture cannot be accepted as real, single-venue replay evidence."""


def inspect_capture(pcap: Path, venue: str, symbol: str) -> dict:
    """Validate upstream metadata and a single unmodified capture's identity.

    Does NOT validate price sequence. The actual upstream Replayer does that.
    This check must run before any file is passed to upstream playback.
    """
    pcap = Path(pcap)
    if not pcap.name.endswith(".pcap.zst"):
        raise CaptureRejected("EXPECTED_UPSTREAM_COMPRESSED_PCAP")
    if not pcap.is_file() or pcap.stat().st_size < 100:
        raise CaptureRejected("MISSING_OR_EMPTY_SOURCE_PCAP")
    meta = Path(str(pcap)[:-len(".pcap.zst")] + ".meta.json")
    if not meta.is_file() or meta.stat().st_size < 20:
        raise CaptureRejected("MISSING_OR_EMPTY_SOURCE_METADATA")

    try:
        metadata = json.loads(meta.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError, OSError) as exc:
        raise CaptureRejected("INVALID_SOURCE_METADATA") from exc
    if not isinstance(metadata, dict) or metadata.get("version") != 1:
        raise CaptureRejected("WRONG_METADATA_SCHEMA")
    if metadata.get("cryptofeed_version") != "3.0.5":
        raise CaptureRejected("UNPINNED_CAPTURE_PRODUCER")
    if metadata.get("files") != [pcap.name]:
        raise CaptureRejected("ROTATED_OR_MISMATCHED_PCAP_FILES")
    feeds = metadata.get("feeds")
    if not isinstance(feeds, list) or len(feeds) != 1:
        raise CaptureRejected("REQUIRES_ONE_EXCHANGE_FEED")
    feed = feeds[0]
    if (not isinstance(feed, dict) or feed.get("exchange") != venue or
        feed.get("symbols") != [symbol]):
        raise CaptureRejected("WRONG_VENUE_OR_SYMBOL")
    channels = feed.get("channels")
    if not isinstance(channels, list) or not {"trades", "l2_book"}.issubset(set(channels)):
        raise CaptureRejected("REQUIRED_CHANNELS_NOT_RECORDED")

    streams = metadata.get("streams")
    if not isinstance(streams, list) or not streams:
        raise CaptureRejected("MISSING_CAPTURE_STREAMS")
    if any(not isinstance(s, dict) or s.get("exchange") != venue for s in streams):
        raise CaptureRejected("MULTI_VENUE_OR_INVALID_STREAM")
    if not any(s.get("kind") == "ws" and s.get("messages", 0) > 0 for s in streams):
        raise CaptureRejected("NO_RECORDED_EXCHANGE_WEBSOCKET_MESSAGES")

    return {
        "venue": venue, "symbol": symbol,
        "pcap_sha256": hashlib.sha256(pcap.read_bytes()).hexdigest(),
        "pcap_bytes": pcap.stat().st_size,
        "recorded_ws_messages": sum(s.get("messages", 0) for s in streams if s.get("kind") == "ws"),
        "recorded_ws_streams": sum(s.get("kind") == "ws" for s in streams),
        "capture_version": metadata["cryptofeed_version"],
    }


@dataclass
class ReplayWitness:
    venue: str
    symbol: str
    trades: int = 0
    books: int = 0
    invalid: int = 0
    seen_trade_ids: set = field(default_factory=set)
    final_bid: Decimal | None = None
    final_ask: Decimal | None = None

    def on_trade(self, event, receipt: float):
        if (getattr(event, "exchange", None) != self.venue
            or getattr(event, "symbol", None) != self.symbol
            or str(getattr(event, "side", "")).lower() not in ("buy", "sell")
            or not positive_number(getattr(event, "price", None))
            or not positive_number(getattr(event, "amount", None))
            or not acceptable_time(getattr(event, "timestamp", None), receipt, receipt)):
            self.invalid += 1
            return
        tid = getattr(event, "id", None)
        if tid is None or tid in self.seen_trade_ids:
            self.invalid += 1
            return
        self.seen_trade_ids.add(tid)
        self.trades += 1

    def on_book(self, event, receipt: float):
        if (getattr(event, "exchange", None) != self.venue
            or getattr(event, "symbol", None) != self.symbol
            or not acceptable_time(getattr(event, "timestamp", None), receipt, receipt)):
            self.invalid += 1
            return
        try:
            book = event.book
            bid, bsize = book.bids.index(0)
            ask, asize = book.asks.index(0)
            if not all(positive_number(x) for x in (bid, ask, bsize, asize)):
                raise ValueError("BAD_TOP_LEVEL")
            if Decimal(bid) >= Decimal(ask):
                raise ValueError("CROSSED_BOOK")
        except (AttributeError, IndexError, ValueError, TypeError, OverflowError):
            self.invalid += 1
            return
        self.books += 1
        self.final_bid = Decimal(bid)
        self.final_ask = Decimal(ask)

    def checks(self, result) -> dict:
        counts = getattr(result, "callbacks", {})
        if (self.invalid or self.trades < 1 or self.books < 1
            or int(getattr(result, "order_regressions", 1)) != 0
            or int(getattr(result, "messages_processed", 0)) <= 0
            or counts.get("trades") != self.trades
            or counts.get("l2_book") != self.books):
            raise CaptureRejected("REPLAY_SOURCE_QUALITY_OR_COUNTS_REJECTED")
        return {
            "trades": self.trades,
            "books": self.books,
            "messages_processed": int(result.messages_processed),
            "http_requests_served": int(result.http_requests_served),
            "order_regressions": int(result.order_regressions),
            "last_bid": str(self.final_bid),
            "last_ask": str(self.final_ask),
        }


def replay_once(pcap: Path, venue: str, symbol: str) -> dict:
    from cryptofeed.capture import playback
    from cryptofeed.defines import L2_BOOK, TRADES

    witness = ReplayWitness(venue, symbol)

    async def trade_callback(event, receipt):
        witness.on_trade(event, receipt)

    async def book_callback(event, receipt):
        witness.on_book(event, receipt)

    result = playback(
        str(pcap), exchange=venue,
        callbacks={TRADES: trade_callback, L2_BOOK: book_callback},
        on_error="raise", strict_order=True, pacing="fast",
    )
    return witness.checks(result)


def verify(pcap: Path, venue: str, symbol: str, repeat: int = 2) -> dict:
    manifest = inspect_capture(pcap, venue, symbol)
    if repeat not in (1, 2):
        raise CaptureRejected("ONLY_ONE_OR_TWO_REPLAY_PASSES")
    trials = [replay_once(pcap, venue, symbol) for _ in range(repeat)]
    if any(t != trials[0] for t in trials[1:]):
        raise CaptureRejected("NON_DETERMINISTIC_UPSTREAM_REPLAY")
    return {
        "status": "VERIFIED_REAL_CAPTURE_REPLAY",
        "source": "cryptofeed_3.0.5_official_replayer",
        **manifest, **trials[0],
        "replay_passes": repeat,
        "synthetic_market_data": False,
        "orders_enabled": False,
        "strategy_performance_tested": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay upstream Kraken Spot L2/Trades PCAP offline")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--venue", default="KRAKEN", choices=("KRAKEN",))
    parser.add_argument("--symbol", default="BTC-USD", choices=("BTC-USD",))
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON verification output")
    args = parser.parse_args()
    try:
        report = verify(args.capture, args.venue, args.symbol, args.repeat)
        code = 0
    except Exception as exc:
        report = {"status": "REPLAY_NOT_VERIFIED",
                  "reason": str(exc) if isinstance(exc, CaptureRejected) else type(exc).__name__,
                  "orders_enabled": False, "synthetic_market_data": False}
        code = 1
    line = json.dumps(report, sort_keys=True, separators=(",", ":"))
    print(line)
    if args.out is not None:
        args.out.write_text(line + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
