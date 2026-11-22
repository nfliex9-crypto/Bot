"""Tests for operational readiness only; not simulated trading performance."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_live import Evidence, valid_number


class ExternalEvidenceTests(unittest.TestCase):
    def test_empty_streams_fail(self):
        d = Evidence("KRAKEN", "BTC-USD").summary(now=100)
        self.assertEqual(d["status"], "DATA_UNVERIFIED")
        self.assertFalse(d["orders_enabled"])
        self.assertFalse(d["synthetic_market_data"])

    def test_one_channel_only_fails(self):
        e = Evidence("KRAKEN", "BTC-USD", trades=4, latest_trade_receipt=95)
        self.assertEqual(e.summary(now=100)["status"], "DATA_UNVERIFIED")

    def test_both_external_channels_recent_pass(self):
        e = Evidence(
            "KRAKEN", "BTC-USD",
            trades=10, books=11,
            latest_trade_receipt=98,
            latest_book_receipt=99,
            latest_bid=50000,
            latest_ask=50000.1,
        )
        r = e.summary(now=100)
        self.assertEqual(r["status"], "VERIFIED_RECENT_EXTERNAL_EVENTS")
        self.assertFalse(r["orders_enabled"])

    def test_stale_or_future_timestamps_fail(self):
        e = Evidence("KRAKEN", "BTC-USD", trades=2, books=2,
                     latest_trade_receipt=70, latest_book_receipt=70,
                     latest_bid=100, latest_ask=101)
        self.assertEqual(e.summary(now=100)["status"], "DATA_UNVERIFIED")
        e.latest_trade_receipt = 101
        e.latest_book_receipt = 101
        self.assertEqual(e.summary(now=100)["status"], "DATA_UNVERIFIED")

    def test_crossed_book_fails(self):
        e = Evidence("KRAKEN", "BTC-USD", trades=2, books=2,
                     latest_trade_receipt=99, latest_book_receipt=99,
                     latest_bid=101, latest_ask=100)
        self.assertEqual(e.summary(now=100)["status"], "DATA_UNVERIFIED")

    def test_bad_event_fails(self):
        e = Evidence("KRAKEN", "BTC-USD", trades=2, books=2,
                     latest_trade_receipt=99, latest_book_receipt=99,
                     latest_bid=100, latest_ask=101, invalid_events=1)
        self.assertEqual(e.summary(now=100)["status"], "DATA_UNVERIFIED")

    def test_reject_bad_numbers(self):
        self.assertFalse(valid_number(float("nan")))
        self.assertFalse(valid_number(float("inf")))
        self.assertFalse(valid_number(0))
        self.assertFalse(valid_number("invalid"))
        self.assertTrue(valid_number("0.001"))


if __name__ == "__main__":
    unittest.main()
