"""Contract tests with opaque fake objects, NOT synthetic market-data evidence."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_live import Evidence, acceptable_time, positive_number


def trade(*, venue="KRAKEN", symbol="BTC-USD", price="100", amount="2", side="buy", ts=98):
    return NS(exchange=venue, symbol=symbol, price=price, amount=amount, side=side, timestamp=ts)


def book(*, venue="KRAKEN", symbol="BTC-USD", bid="100", ask="101", bid_qty="4", ask_qty="5", ts=99):
    class Side:
        def __init__(self, levels): self.levels = levels
        def __bool__(self): return bool(self.levels)
        def index(self, idx): return self.levels[idx]
    return NS(exchange=venue, symbol=symbol, timestamp=ts,
              book=NS(bids=Side([(bid, bid_qty)]), asks=Side([(ask, ask_qty)])))


class ExternalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.e = Evidence("KRAKEN", "BTC-USD")

    def valid(self):
        self.e.observe_trade(trade(), 99.0, now=100)
        self.e.observe_book(book(), 99.5, now=100)

    def assert_unverified(self):
        self.assertEqual(self.e.summary(now=100)["status"], "DATA_UNVERIFIED")

    def test_no_streams_fail_closed(self):
        self.assert_unverified()
        self.assertFalse(self.e.summary(now=100)["orders_enabled"])

    def test_one_channel_only_fails(self):
        self.e.observe_trade(trade(), 99, now=100)
        self.assert_unverified()

    def test_valid_venue_events_pass_no_order_permission(self):
        self.valid()
        result = self.e.summary(now=100)
        self.assertEqual(result["status"], "VERIFIED_RECENT_EXTERNAL_EVENTS")
        self.assertEqual((result["best_bid"], result["best_ask"]), (100.0, 101.0))
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["synthetic_market_data"])

    def test_wrong_venue_trade_blocks(self):
        self.valid()
        self.e.observe_trade(trade(venue="BINANCE"), 99, now=100)
        self.assertEqual(self.e.invalid_events, 1)
        self.assert_unverified()

    def test_wrong_pair_book_blocks(self):
        self.valid()
        self.e.observe_book(book(symbol="ETH-USD"), 99, now=100)
        self.assert_unverified()

    def test_crossed_and_locked_book_fail(self):
        for ask in ("100", "99"):
            e = Evidence("KRAKEN", "BTC-USD")
            e.observe_book(book(ask=ask), 99, now=100)
            self.assertEqual(e.invalid_events, 1)

    def test_bad_quantity_or_price_fail(self):
        for kwargs in ({"bid_qty": "0"}, {"bid": "nan"}, {"ask_qty": "inf"}):
            e = Evidence("KRAKEN", "BTC-USD")
            e.observe_book(book(**kwargs), 99, now=100)
            self.assertEqual(e.invalid_events, 1)

    def test_stale_trade_event_fail(self):
        self.e.observe_trade(trade(ts=50), 99, now=100)
        self.assertEqual(self.e.invalid_events, 1)

    def test_future_timestamp_fail(self):
        self.e.observe_book(book(ts=200), 99, now=100)
        self.assertEqual(self.e.invalid_events, 1)

    def test_missing_timestamp_fail(self):
        self.e.observe_trade(trade(ts=None), 99, now=100)
        self.assertEqual(self.e.invalid_events, 1)

    def test_stale_after_a_valid_window_fail(self):
        self.valid()
        self.assertEqual(self.e.summary(now=117)["status"], "DATA_UNVERIFIED")

    def test_zero_price_and_unknown_trade_side_fail(self):
        for kwargs in ({"side": "unknown"}, {"price": "0"}, {"amount": -1}):
            e = Evidence("KRAKEN", "BTC-USD")
            e.observe_trade(trade(**kwargs), 99, now=100)
            self.assertEqual(e.invalid_events, 1)

    def test_valid_number_rejection(self):
        for value in (None, 0, -1, "not-a-number", float("nan"), float("inf")):
            self.assertFalse(positive_number(value))
        self.assertTrue(positive_number("0.0001"))

    def test_event_time_invariant(self):
        self.assertFalse(acceptable_time(105, 90, 100))
        self.assertFalse(acceptable_time(60, 95, 100))
        self.assertTrue(acceptable_time(98, 99, 100))


if __name__ == "__main__":
    unittest.main()
