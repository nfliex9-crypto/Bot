"""Read-only DEMO native-history exporter unit tests with fake MT5."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("mt5_export", Path(__file__).with_name("export_history.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 60
    def __init__(self, trade_mode=0):
        self.trade_mode = trade_mode
        self.calls = []
    def account_info(self):
        return SimpleNamespace(trade_mode=self.trade_mode,server="DemoServer",login=12233445)
    def terminal_info(self):
        return SimpleNamespace(connected=True)
    def symbol_info(self, symbol):
        return SimpleNamespace(point=0.01)
    def symbol_select(self, symbol, selected):
        return True
    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.calls.append((symbol,timeframe,start,count))
        return [
            {"time":1800000000,"open":100,"high":101,"low":99,"close":100.5,"spread":12,"tick_volume":33},
            {"time":1800000900,"open":100.5,"high":102,"low":100,"close":101,"spread":0,"tick_volume":45},
        ]


class NativeHistoryTests(unittest.TestCase):
    def test_only_closed_demo_history_with_price_unit_spread(self):
        provider=MT5()
        data=module.extract(provider,"XAUUSD","M15",1200,now=1800001000)
        self.assertEqual(provider.calls,[("XAUUSD",15,1,1200)])
        self.assertEqual(len(data["candles"]),1)
        self.assertAlmostEqual(data["candles"][0]["spread"],0.12)
        self.assertEqual(data["orders_executed"],0)
        self.assertEqual(data["trade_mode"],"demo")
        self.assertEqual(data["account_last4"],"3445")
    def test_rejects_real_account_before_fetch(self):
        provider=MT5(trade_mode=2)
        with self.assertRaisesRegex(RuntimeError,"DEMO_ACCOUNT_REQUIRED"):
            module.extract(provider,"XAUUSD","H1")
        self.assertEqual(provider.calls,[])
    def test_input_whitelist(self):
        with self.assertRaisesRegex(ValueError,"INVALID_NATIVE_SYMBOL"):
            module.extract(MT5(),"../../secret","M15")
        with self.assertRaisesRegex(ValueError,"INVALID_NATIVE_HISTORY_REQUEST"):
            module.extract(MT5(),"XAUUSD","M1")


if __name__=="__main__":
    unittest.main()
