"""Offline tests of independent status server and cross-project isolation."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace

from server import status_for_dashboard
from collector import snapshot

SYM = "BTC/USDT:USDT"
NOW = 1_800_000_000_000


class DashboardSourceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "status.json"

    def write(self, payload):
        self.file.write_text(json.dumps(payload))

    def valid(self):
        return {"venue": "WEEX", "market_type": "USDT_LINEAR_PERPETUAL",
                "markets": {SYM: {
                    "received_ms": NOW-1500, "bid": 100, "ask": 101,
                    "last": 100.5, "trades_seen": 42,
                    "verified_source": "CCXT_PRO_WEEX_PUBLIC_FUTURES"}}}

    def test_missing_data_never_generates_fake_prices(self):
        result = status_for_dashboard(self.file, NOW)
        self.assertEqual(result["markets"], {})
        self.assertEqual(result["execution"], "DISABLED")
        self.assertEqual(result["demo_account"], "NOT_CONNECTED")

    def test_real_venue_source_and_freshness_required(self):
        self.write(self.valid())
        result = status_for_dashboard(self.file, NOW)
        self.assertEqual(result["markets"][SYM]["status"], "LIVE")
        self.assertEqual(result["markets"][SYM]["last"], 100.5)

    def test_older_than_15_seconds_is_unavailable(self):
        d = self.valid()
        d["markets"][SYM]["received_ms"] = NOW-15100
        self.write(d)
        self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_spot_not_accepted(self):
        d = self.valid()
        d["market_type"] = "SPOT"
        self.write(d)
        self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_foreign_venue_not_accepted(self):
        d = self.valid()
        d["venue"] = "KRAKEN"
        self.write(d)
        self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_fabricated_source_not_accepted(self):
        d = self.valid()
        d["markets"][SYM]["verified_source"] = "MANUAL"
        self.write(d)
        self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_negative_and_crossed_books_are_unavailable(self):
        for bid, ask in ((101,100),(-1,101),(100,0)):
            with self.subTest(bid=bid, ask=ask):
                d = self.valid()
                d["markets"][SYM]["bid"] = bid
                d["markets"][SYM]["ask"] = ask
                self.write(d)
                self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_corrupt_json_unavailable(self):
        self.file.write_text("not-json")
        self.assertEqual(status_for_dashboard(self.file, NOW)["markets"], {})

    def test_readonly_collector_snapshot_omits_stale_markets(self):
        now = NOW/1000
        ev = SimpleNamespace(
            invalid=0,unique_trades=100,book_updates=20,
            latest_book_receipt=now-1,latest_trade_receipt=now-1,
            last_bid=100,last_ask=101,last_trade=100.5)
        record = snapshot({SYM: ev},now)
        self.assertFalse(record["orders_enabled"])
        self.assertIn(SYM,record["markets"])
        ev.latest_trade_receipt=now-20
        self.assertNotIn(SYM,snapshot({SYM:ev},now)["markets"])


if __name__ == "__main__":
    unittest.main()
