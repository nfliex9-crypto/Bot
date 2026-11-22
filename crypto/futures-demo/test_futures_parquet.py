"""Deterministic schema/integrity tests. Fixtures are NOT exchange data."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from weex_futures_parquet import (
    CaptureRejected, ParquetCapture, book_record, trade_record,
    validate_levels, validate_timestamp, verify_capture, hash_file,
)


class ParquetFormatTests(unittest.TestCase):
    symbol = "BTC/USDT:USDT"
    received = 1_800_000_000_000

    @staticmethod
    def book():
        return {
            "timestamp": 1_799_999_999_000,
            "nonce": 400,
            "bids": [[100, 1.5], [99, 2]],
            "asks": [[101, 0.5], [102, 1]],
        }

    @classmethod
    def trade(cls):
        return {"id": "testonly-123", "symbol": cls.symbol, "side": "buy",
                "price": 100.5, "amount": 0.01,
                "timestamp": 1_799_999_999_500}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "sample.parquet"

    def write_good(self):
        writer = ParquetCapture(self.target, self.symbol, flush_rows=64)
        writer.write_book(self.book(), self.received)
        writer.write_trades([self.trade(), self.trade()], self.received)
        self.assertEqual(writer.books, 1)
        self.assertEqual(writer.trades, 1)
        self.assertEqual(writer.close(success=True), self.target)
        self.target.with_suffix(".manifest.json").write_text(json.dumps({
            "venue": "WEEX", "market": "USDT_LINEAR_PERPETUAL",
            "symbol": self.symbol, "rows": 2, "book_rows": 1, "trade_rows": 1,
            "sha256": hash_file(self.target),
        }), encoding="utf-8")

    def test_book_levels_and_source(self):
        event = book_record(self.book(), self.symbol, self.received)
        self.assertEqual(event["venue"], "WEEX")
        self.assertEqual(event["market"], "USDT_LINEAR_PERPETUAL")
        self.assertEqual(event["best_bid"], 100)
        self.assertEqual(event["best_ask"], 101)
        self.assertEqual(len(event["bids"]), 2)

    def test_executed_trade_no_price_inference(self):
        event = trade_record(self.trade(), self.symbol, self.received)
        self.assertEqual(event["trade_id"], "testonly-123")
        self.assertIsNone(event["best_bid"])
        self.assertEqual(event["side"], "buy")

    def test_native_parquet_roundtrip_and_dedup(self):
        self.write_good()
        report = verify_capture(self.target, self.symbol)
        self.assertEqual(report["status"], "VERIFIED_WEEX_REAL_FUTURES_PARQUET")
        self.assertEqual((report["book_rows"], report["trade_rows"]), (1, 1))
        self.assertFalse(report["orders_enabled"])

    def test_tampered_data_rejected_by_sha(self):
        self.write_good()
        with self.target.open("ab") as h:
            h.write(b"TAMPER")
        with self.assertRaisesRegex(CaptureRejected, "CAPTURE_HASH_OR_MARKET_MISMATCH"):
            verify_capture(self.target, self.symbol)

    def test_wrong_market_manifest_rejected(self):
        self.write_good()
        p = self.target.with_suffix(".manifest.json")
        obj = json.loads(p.read_text())
        obj["market"] = "SPOT"
        p.write_text(json.dumps(obj))
        with self.assertRaises(CaptureRejected):
            verify_capture(self.target, self.symbol)

    def test_truncated_row_manifest_rejected(self):
        self.write_good()
        p = self.target.with_suffix(".manifest.json")
        obj = json.loads(p.read_text())
        obj["rows"] = 1000
        p.write_text(json.dumps(obj))
        with self.assertRaisesRegex(CaptureRejected, "INCOMPLETE_FUTURES"):
            verify_capture(self.target, self.symbol)

    def test_partial_unverified_file_not_promoted(self):
        w = ParquetCapture(self.target, self.symbol)
        w.write_book(self.book(), self.received)
        self.assertIsNone(w.close(success=False))
        self.assertFalse(self.target.exists())
        self.assertTrue(Path(str(self.target)+".partial").exists())

    def test_reject_stale_exchange_event(self):
        stale = self.book()
        stale["timestamp"] = self.received - 35_000
        with self.assertRaises(CaptureRejected):
            book_record(stale, self.symbol, self.received)

    def test_reject_missing_trade_id(self):
        bad = self.trade()
        bad.pop("id")
        with self.assertRaises(CaptureRejected):
            trade_record(bad, self.symbol, self.received)

    def test_reject_wrong_traded_contract(self):
        bad = self.trade()
        bad["symbol"] = "BTC/USDT"
        with self.assertRaises(CaptureRejected):
            trade_record(bad, self.symbol, self.received)

    def test_reject_unsorted_ladder(self):
        book = self.book()
        book["bids"] = [[99, 1], [100, 1]]
        with self.assertRaises(CaptureRejected):
            validate_levels(book, 15)

    def test_reject_crossed_book(self):
        book = self.book()
        book["bids"] = [[105, 1]]
        with self.assertRaises(CaptureRejected):
            validate_levels(book, 15)

    def test_refuse_overwriting_finished_capture(self):
        self.write_good()
        with self.assertRaises(CaptureRejected):
            ParquetCapture(self.target, self.symbol)

if __name__ == "__main__":
    unittest.main()
