"""Synthetic fixtures verify code contracts only, NEVER reported as market proof."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from weex_futures_feed import verify_swap, FutureEvidence

class MarketTypeTests(unittest.TestCase):
    def market(self):
        return dict(symbol="BTC/USDT:USDT",swap=True,contract=True,spot=False,
                    settle="USDT",linear=True,active=True)

    def test_perpetual_accepted(self):
        self.assertTrue(verify_swap(self.market(),"BTC/USDT:USDT"))

    def test_spot_rejected(self):
        m=self.market();m.update(swap=False,contract=False,spot=True)
        with self.assertRaises(ValueError):verify_swap(m,"BTC/USDT:USDT")

    def test_wrong_settlement_rejected(self):
        m=self.market();m["settle"]="USD"
        with self.assertRaises(ValueError):verify_swap(m,"BTC/USDT:USDT")

    def test_wrong_symbol_rejected(self):
        with self.assertRaises(ValueError):verify_swap(self.market(),"ETH/USDT:USDT")

    def test_inactive_rejected(self):
        m=self.market();m["active"]=False
        with self.assertRaises(ValueError):verify_swap(m,"BTC/USDT:USDT")

    def test_future_events_required(self):
        d=FutureEvidence("BTC/USDT:USDT")
        self.assertEqual(d.report(100,40)["status"],"DATA_UNVERIFIED")

    def test_trade_and_book_pass(self):
        d=FutureEvidence("BTC/USDT:USDT")
        d.book({"bids":[[99,2]],"asks":[[101,3]],"timestamp":100000},100)
        d.trades([{"symbol":"BTC/USDT:USDT","side":"buy","price":100,
                   "amount":0.01,"timestamp":100000,"id":"T1"}],100)
        self.assertEqual(d.report(101,40)["status"],"LIVE_WEEX_PERP_FEED_VERIFIED")

    def test_duplicate_trade_not_double_counted(self):
        d=FutureEvidence("BTC/USDT:USDT")
        t={"symbol":"BTC/USDT:USDT","side":"sell","price":100,"amount":2,"timestamp":100000,"id":"T1"}
        d.trades([t,t],100)
        self.assertEqual(d.unique_trades,1)

    def test_crossed_book_rejected(self):
        d=FutureEvidence("BTC/USDT:USDT")
        d.book({"bids":[[101,2]],"asks":[[100,2]]},100)
        self.assertEqual(d.invalid,1)

    def test_stale_receipt_rejected(self):
        d=FutureEvidence("BTC/USDT:USDT")
        d.book({"bids":[[99,2]],"asks":[[101,3]]},100)
        d.trades([{"symbol":"BTC/USDT:USDT","side":"buy","price":100,
                   "amount":1,"id":"X"}],100)
        self.assertEqual(d.report(119,40)["status"],"DATA_UNVERIFIED")

    def test_stale_exchange_trade_rejected(self):
        d=FutureEvidence("BTC/USDT:USDT")
        d.trades([{"symbol":"BTC/USDT:USDT","side":"buy","price":100,
                   "amount":1,"id":"X","timestamp":10_000}],100)
        self.assertEqual(d.invalid,1)

    def test_no_trade_id_not_falsely_counted(self):
        d=FutureEvidence("BTC/USDT:USDT")
        d.trades([{"symbol":"BTC/USDT:USDT","side":"buy","price":100,
                   "amount":1}],100)
        self.assertEqual(d.unique_trades,0)

if __name__=="__main__":
    unittest.main()
