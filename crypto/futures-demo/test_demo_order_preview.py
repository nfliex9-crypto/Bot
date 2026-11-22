"""No-network previews: no funds, API credentials or order placement."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from weex_demo_order_preview import PreviewRejected, preview_order
from weex_demo_guard import SandboxBoundaryError


class FakeClient:
    def __init__(self, host="https://api-sim.weex.com"):
        self.host = host
        self.calls = 0

    def create_contract_order_request(self, symbol, typ, side, amount, price, params):
        self.calls += 1
        return {"symbol": "BTCUSDT", "side": side.upper(), "type": "LIMIT",
                "quantity": "1", "price": str(price), **params}

    def sign(self, path, api, method, params):
        return {"url": self.host + "/" + path, "method": method, "body": params}


class DemoPreviewTests(unittest.TestCase):
    symbol = "BTC/USDT:USDT"

    def market(self):
        return {
            "symbol": self.symbol, "id": "BTCUSDT", "swap": True,
            "contract": True, "spot": False, "settle": "USDT",
            "linear": True, "active": True,
            "limits": {"amount": {"min": 1}},
        }

    def book(self):
        return {"bids": [[100, 3]], "asks": [[101, 5]]}

    def test_pure_upstream_preview_zero_orders(self):
        r = preview_order(FakeClient(), self.symbol, "buy", self.market(), self.book())
        self.assertEqual(r["destination_host"], "api-sim.weex.com")
        self.assertEqual(r["simulated_exchange_orders_placed"], 0)
        self.assertEqual(r["actual_http_requests_sent_for_order"], 0)
        self.assertTrue(r["read_only"])

    def test_short_sell_preview_uses_ask(self):
        r = preview_order(FakeClient(), self.symbol, "sell", self.market(), self.book())
        self.assertEqual(r["order_side"], "sell")
        self.assertEqual(r["candidate_price_not_submitted"], "101.0")

    def test_production_host_rejected(self):
        with self.assertRaises(SandboxBoundaryError):
            preview_order(FakeClient("https://api-contract.weex.com"),
                          self.symbol, "buy", self.market(), self.book())

    def test_no_market_minimum_rejected(self):
        m = self.market()
        m["limits"]["amount"]["min"] = None
        with self.assertRaises(PreviewRejected):
            preview_order(FakeClient(), self.symbol, "buy", m, self.book())

    def test_wrong_instrument_rejected(self):
        with self.assertRaises(ValueError):
            preview_order(FakeClient(), "BTC/USDT", "buy", self.market(), self.book())

    def test_spot_contract_rejected(self):
        m = self.market()
        m["spot"] = True
        m["swap"] = False
        with self.assertRaises(ValueError):
            preview_order(FakeClient(), self.symbol, "buy", m, self.book())

    def test_crossed_book_rejected(self):
        b = self.book()
        b["bids"][0][0] = 102
        with self.assertRaises(PreviewRejected):
            preview_order(FakeClient(), self.symbol, "buy", self.market(), b)

    def test_invalid_direction_rejected(self):
        with self.assertRaises(PreviewRejected):
            preview_order(FakeClient(), self.symbol, "hold", self.market(), self.book())


if __name__ == "__main__":
    unittest.main()
