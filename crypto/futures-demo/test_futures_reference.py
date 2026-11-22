"""No-network tests. Values are fixtures only; NEVER claimed as live quotes."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from weex_futures_reference import (
    ReferenceRejected, build_reference, finite_value, recent_millis
)

class ReferenceTests(unittest.TestCase):
    now = 1_800_000_000_000
    symbol = "BTC/USDT:USDT"

    def fixture(self):
        return (
            dict(symbol=self.symbol, last=100.0, timestamp=self.now-1000),
            dict(symbol=self.symbol, markPrice=99.0, indexPrice=98.0,
                 fundingRate=-0.00025, nextFundingRate=0.00015,
                 timestamp=self.now-1000, nextFundingTimestamp=self.now+3_600_000),
            dict(symbol=self.symbol, openInterestAmount=100000.0, timestamp=self.now-1000),
        )

    def test_distinguishes_last_mark_index_and_funding(self):
        r = build_reference(self.symbol, *self.fixture(), now_ms=self.now)
        self.assertEqual(r["last_futures_price"], 100.0)
        self.assertEqual(r["mark_price"], 99.0)
        self.assertEqual(r["index_price"], 98.0)
        self.assertEqual(r["last_funding_rate"], -0.00025)
        self.assertEqual(r["forecast_funding_rate"], 0.00015)
        self.assertGreater(r["last_vs_mark_bps"], 0)
        self.assertGreater(r["mark_vs_index_bps"], 0)
        self.assertFalse(r["orders_enabled"])
        self.assertFalse(r["uses_spot_price"])

    def test_rejects_wrong_symbol_in_any_source(self):
        for idx in range(3):
            rows=list(self.fixture())
            rows[idx]["symbol"]="ETH/USDT:USDT"
            with self.assertRaises(ReferenceRejected):
                build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_missing_mark_and_index_independently(self):
        for field in ("markPrice","indexPrice"):
            rows=list(self.fixture())
            rows[1].pop(field)
            with self.assertRaises(ReferenceRejected):
                build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_old_funding_reference(self):
        rows=list(self.fixture())
        rows[1]["timestamp"]=self.now-181_000
        with self.assertRaises(ReferenceRejected):
            build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_stale_open_interest(self):
        rows=list(self.fixture())
        rows[2]["timestamp"]=self.now-181_000
        with self.assertRaises(ReferenceRejected):
            build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_stale_futures_ticker(self):
        rows=list(self.fixture())
        rows[0]["timestamp"]=self.now-181_000
        with self.assertRaises(ReferenceRejected):
            build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_nan_and_zero_positive_price(self):
        for number in ("nan","inf",0,-1,None):
            with self.assertRaises(ReferenceRejected):
                finite_value(number,positive=True)

    def test_allows_negative_funding(self):
        self.assertEqual(finite_value("-0.0001"),-0.0001)

    def test_rejects_future_exchange_time(self):
        with self.assertRaises(ReferenceRejected):
            recent_millis(self.now+20_000,self.now)

    def test_forecast_optional_but_not_mislabelled(self):
        rows=list(self.fixture())
        rows[1]["nextFundingRate"]=None
        r=build_reference(self.symbol,*rows,now_ms=self.now)
        self.assertIsNone(r["forecast_funding_rate"])
        self.assertEqual(r["last_funding_rate"],-0.00025)

    def test_rejects_missing_funding(self):
        rows=list(self.fixture())
        rows[1]["fundingRate"]=None
        with self.assertRaises(ReferenceRejected):
            build_reference(self.symbol,*rows,now_ms=self.now)

    def test_rejects_nonpositive_open_interest(self):
        rows=list(self.fixture())
        rows[2]["openInterestAmount"]=0
        with self.assertRaises(ReferenceRejected):
            build_reference(self.symbol,*rows,now_ms=self.now)

if __name__ == "__main__":
    unittest.main()
