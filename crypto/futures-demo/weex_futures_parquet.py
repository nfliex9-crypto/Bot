"""Genuine WEEX linear USDT perpetual L2 and executed trade capture.

Upstream CCXT Pro owns websocket, subscription, sequencing, orderbook merge;
upstream Apache Arrow writes native Parquet. This is transport/storage glue only.
No synthetic ticks, no Spot book, no demo account calls, no execution routes.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from weex_futures_feed import PAIRS, verify_swap, positive

SOURCE = "ccxt_4.5.93_weex_public_perpetual_ws"
MAX_TRADE_IDS = 100_000


class CaptureRejected(ValueError):
    pass


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def arrow_schema():
    import pyarrow as pa
    level = pa.struct([pa.field("price", pa.float64()),
                       pa.field("amount", pa.float64())])
    return pa.schema([
        pa.field("venue", pa.string(), nullable=False),
        pa.field("market", pa.string(), nullable=False),
        pa.field("symbol", pa.string(), nullable=False),
        pa.field("origin", pa.string(), nullable=False),
        pa.field("kind", pa.string(), nullable=False),
        pa.field("exchange_timestamp_ms", pa.int64(), nullable=False),
        pa.field("received_timestamp_ms", pa.int64(), nullable=False),
        pa.field("sequence", pa.string()),
        pa.field("trade_id", pa.string()),
        pa.field("side", pa.string()),
        pa.field("price", pa.float64()),
        pa.field("amount", pa.float64()),
        pa.field("best_bid", pa.float64()),
        pa.field("best_ask", pa.float64()),
        pa.field("bids", pa.list_(level)),
        pa.field("asks", pa.list_(level)),
    ])


def validate_timestamp(timestamp, received_ms):
    try:
        ts = int(timestamp)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CaptureRejected("MISSING_EXCHANGE_TIMESTAMP") from exc
    if ts < 1_600_000_000_000 or ts > received_ms + 15000 or received_ms - ts > 30000:
        raise CaptureRejected("STALE_OR_FUTURE_EXCHANGE_EVENT")
    return ts


def validate_levels(orderbook, depth: int):
    try:
        bids = orderbook["bids"][:depth]
        asks = orderbook["asks"][:depth]
        if not bids or not asks:
            raise ValueError("EMPTY_BOOK")
        if len(bids) > depth or len(asks) > depth:
            raise ValueError("BAD_DEPTH")
        def levels(rows):
            result = []
            for row in rows:
                price, amount = row[:2]
                if not (positive(price) and positive(amount)):
                    raise ValueError("BAD_BOOK_LEVEL")
                result.append({"price": float(price), "amount": float(amount)})
            return result
        b = levels(bids)
        a = levels(asks)
        if b[0]["price"] >= a[0]["price"]:
            raise ValueError("CROSSED_BOOK")
        if any(b[i]["price"] <= b[i+1]["price"] for i in range(len(b)-1)):
            raise ValueError("UNSORTED_BID_LEVELS")
        if any(a[i]["price"] >= a[i+1]["price"] for i in range(len(a)-1)):
            raise ValueError("UNSORTED_ASK_LEVELS")
        return b, a
    except (KeyError, TypeError, IndexError, OverflowError, ValueError) as exc:
        raise CaptureRejected("BAD_EXTERNAL_ORDERBOOK_LEVELS") from exc


def book_record(entry, symbol: str, received_ms: int, depth: int = 15):
    ts = validate_timestamp(entry.get("timestamp"), received_ms)
    bids, asks = validate_levels(entry, depth)
    return {
        "venue": "WEEX", "market": "USDT_LINEAR_PERPETUAL", "symbol": symbol,
        "origin": SOURCE, "kind": "ORDER_BOOK",
        "exchange_timestamp_ms": ts, "received_timestamp_ms": received_ms,
        "sequence": str(entry["nonce"]) if entry.get("nonce") is not None else None,
        "trade_id": None, "side": None, "price": None, "amount": None,
        "best_bid": bids[0]["price"], "best_ask": asks[0]["price"],
        "bids": bids, "asks": asks,
    }


def trade_record(trade, symbol: str, received_ms: int):
    if trade.get("symbol") != symbol or trade.get("side") not in ("buy", "sell"):
        raise CaptureRejected("FOREIGN_SYMBOL_OR_SIDE")
    if not positive(trade.get("price")) or not positive(trade.get("amount")):
        raise CaptureRejected("INVALID_EXECUTED_TRADE")
    trade_id = trade.get("id")
    if not isinstance(trade_id, (str, int)) or not str(trade_id):
        raise CaptureRejected("EXCHANGE_TRADE_ID_MISSING")
    ts = validate_timestamp(trade.get("timestamp"), received_ms)
    return {
        "venue": "WEEX", "market": "USDT_LINEAR_PERPETUAL", "symbol": symbol,
        "origin": SOURCE, "kind": "TRADE",
        "exchange_timestamp_ms": ts, "received_timestamp_ms": received_ms,
        "sequence": None, "trade_id": str(trade_id), "side": trade["side"],
        "price": float(trade["price"]), "amount": float(trade["amount"]),
        "best_bid": None, "best_ask": None, "bids": None, "asks": None,
    }


class ParquetCapture:
    def __init__(self, dest: Path, symbol: str, flush_rows: int = 256):
        import pyarrow.parquet as pq
        self.dest = Path(dest)
        self.symbol = symbol
        if not 64 <= flush_rows <= 10000:
            raise CaptureRejected("BAD_PARQUET_BUFFER")
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        if self.dest.exists() or self.dest.with_suffix(self.dest.suffix+".partial").exists():
            raise CaptureRejected("REFUSE_OVERWRITE")
        self.partial = self.dest.with_suffix(self.dest.suffix + ".partial")
        self.writer = pq.ParquetWriter(
            str(self.partial), arrow_schema(), compression="zstd")
        self.buffer = []
        self.flush_rows = flush_rows
        self.books = 0
        self.trades = 0
        self.dedup = OrderedDict()
        self.last_book_receipt = 0
        self.last_trade_receipt = 0
        self.finalized = False

    def write_book(self, entry, received_ms, depth=15):
        record = book_record(entry, self.symbol, received_ms, depth)
        self._add(record)
        self.books += 1
        self.last_book_receipt = received_ms

    def write_trades(self, entries, received_ms):
        for event in entries:
            record = trade_record(event, self.symbol, received_ms)
            key = record["trade_id"]
            if key in self.dedup:
                continue
            self.dedup[key] = True
            if len(self.dedup) > MAX_TRADE_IDS:
                self.dedup.popitem(last=False)
            self._add(record)
            self.trades += 1
            self.last_trade_receipt = received_ms

    def _add(self, record):
        self.buffer.append(record)
        if len(self.buffer) >= self.flush_rows:
            self.flush()

    def flush(self):
        import pyarrow as pa
        if self.buffer:
            self.writer.write_table(pa.Table.from_pylist(self.buffer, schema=arrow_schema()))
            self.buffer.clear()

    def close(self, *, success: bool):
        if self.finalized:
            return None
        self.finalized = True
        self.flush()
        self.writer.close()
        if not success or self.books < 1 or self.trades < 1:
            # Keep visibly incomplete output to diagnose, NEVER publish verified parquet.
            return None
        os.replace(self.partial, self.dest)
        return self.dest


def verify_capture(data: Path, symbol: str) -> dict:
    """Read back real Parquet bytes with Arrow, reject loss/truncation/wrong venue."""
    import pyarrow.parquet as pq
    data = Path(data)
    manifest_path = data.with_suffix(".manifest.json")
    if not data.is_file() or not manifest_path.is_file():
        raise CaptureRejected("CAPTURE_OR_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha = hash_file(data)
    if (manifest.get("sha256") != sha or manifest.get("symbol") != symbol
        or manifest.get("venue") != "WEEX" or manifest.get("market") != "USDT_LINEAR_PERPETUAL"):
        raise CaptureRejected("CAPTURE_HASH_OR_MARKET_MISMATCH")
    reader = pq.ParquetFile(data)
    if not reader.schema_arrow.equals(arrow_schema()):
        raise CaptureRejected("PARQUET_SCHEMA_MISMATCH")
    counts = {"ORDER_BOOK": 0, "TRADE": 0}
    trade_ids = set()
    for batch in reader.iter_batches(batch_size=2048):
        for row in batch.to_pylist():
            if (row["venue"] != "WEEX" or row["market"] != "USDT_LINEAR_PERPETUAL"
                or row["symbol"] != symbol or row["origin"] != SOURCE):
                raise CaptureRejected("FOREIGN_OR_FABRICATED_SOURCE")
            validate_timestamp(row["exchange_timestamp_ms"], row["received_timestamp_ms"])
            kind = row["kind"]
            if kind not in counts:
                raise CaptureRejected("UNEXPECTED_EVENT_TYPE")
            counts[kind] += 1
            if kind == "ORDER_BOOK":
                validate_levels({
                    "bids": [(v["price"], v["amount"]) for v in row["bids"]],
                    "asks": [(v["price"], v["amount"]) for v in row["asks"]],
                }, 15)
            else:
                if (row["trade_id"] in trade_ids or
                    not positive(row["price"]) or not positive(row["amount"])):
                    raise CaptureRejected("DUPLICATE_OR_BAD_TRADE")
                trade_ids.add(row["trade_id"])
    if (sum(counts.values()) != manifest.get("rows") or
        counts["ORDER_BOOK"] != manifest.get("book_rows")
        or counts["TRADE"] != manifest.get("trade_rows")
        or not all(counts.values())):
        raise CaptureRejected("INCOMPLETE_FUTURES_TAPE_OR_BOOK")
    return {"status": "VERIFIED_WEEX_REAL_FUTURES_PARQUET",
            "venue": "WEEX", "symbol": symbol, "source": SOURCE,
            "rows": sum(counts.values()), "book_rows": counts["ORDER_BOOK"],
            "trade_rows": counts["TRADE"], "sha256": sha,
            "orders_enabled": False, "synthetic_market_data": False}


async def capture(symbol: str, seconds: int, out_dir: Path, depth=15):
    import ccxt.pro
    exchange = ccxt.pro.weex({
        "enableRateLimit": True, "options": {"defaultType": "swap"},
        "newUpdates": True,
    })
    writer = None
    try:
        await asyncio.wait_for(exchange.load_markets(), timeout=25)
        verify_swap(exchange.market(symbol), symbol)
        session = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stem = symbol.split("/")[0].lower()
        target = Path(out_dir) / f"weex_{stem}_usdt_perp_{session}_{uuid4().hex[:8]}.parquet"
        writer = ParquetCapture(target, symbol)
        end_at = time.monotonic() + seconds
        async def read_books():
            while time.monotonic() < end_at:
                result = await asyncio.wait_for(
                    exchange.watch_order_book(symbol, depth), timeout=20)
                writer.write_book(result, int(time.time()*1000), depth)
        async def read_trades():
            while time.monotonic() < end_at:
                result = await asyncio.wait_for(exchange.watch_trades(symbol), timeout=20)
                writer.write_trades(result, int(time.time()*1000))
        await asyncio.gather(read_books(), read_trades())
        final_ms = int(time.time()*1000)
        fresh = (0 <= final_ms - writer.last_book_receipt <= 15000 and
                 0 <= final_ms - writer.last_trade_receipt <= 15000)
        file = writer.close(success=fresh)
        if not file:
            raise CaptureRejected("NO_RECENT_EXTERNAL_BOOK_AND_TRADES")
        manifest = {
            "schema_version": 1, "venue": "WEEX", "symbol": symbol,
            "market": "USDT_LINEAR_PERPETUAL",
            "source": SOURCE, "source_library": "ccxt==4.5.93",
            "data_file": file.name, "rows": writer.books+writer.trades,
            "book_rows": writer.books, "trade_rows": writer.trades,
            "sha256": hash_file(file),
            "orders_enabled": False, "spot_data_used": False,
        }
        manifest_path = file.with_suffix(".manifest.json")
        partial_manifest = file.with_suffix(".manifest.partial")
        partial_manifest.write_text(
            json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(partial_manifest, manifest_path)
        return verify_capture(file, symbol)
    finally:
        if writer is not None and not writer.finalized:
            writer.close(success=False)
        await exchange.close()


def main():
    parser = argparse.ArgumentParser(description="Native Arrow Parquet capture of WEEX perp L2 & trades")
    parser.add_argument("--symbol", choices=PAIRS, default=PAIRS[0])
    parser.add_argument("--seconds", type=int, default=40)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 3600:
        parser.error("seconds must be between 30 and 3600")
    try:
        result = asyncio.run(capture(args.symbol, args.seconds, args.out_dir))
        code = 0
    except Exception as exc:
        result = {"status": "FUTURES_PARQUET_NOT_VERIFIED",
                  "error_type": type(exc).__name__,
                  "venue": "WEEX", "symbol": args.symbol, "orders_enabled": False}
        code = 1
    print(json.dumps(result,sort_keys=True,separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
