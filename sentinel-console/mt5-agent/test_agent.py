"""Pure unit tests for the Windows-only MT5 monitoring layer."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("sentinel_mt5_agent", Path(__file__).with_name("agent.py"))
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    def __init__(self, trade_mode=0, connected=True):
        self.mode = trade_mode
        self.is_connected = connected
        self.starts = 0
        self.stops = 0
    def initialize(self, *args):
        self.starts += 1
        return True
    def shutdown(self):
        self.stops += 1
    def account_info(self):
        return SimpleNamespace(
            trade_mode=self.mode, login=98765412, server="MetaQuotes-Demo",
            currency="EUR", balance=5000.0, equity=4992.20
        )
    def terminal_info(self):
        return SimpleNamespace(connected=self.is_connected)
    def positions_get(self):
        return [SimpleNamespace(ticket=1)]
    def version(self):
        return (5, 0, 2026)
    def last_error(self):
        return (0, "OK")


class AgentContractTests(unittest.TestCase):
    def test_accepts_demo_only(self):
        monitor = agent.MT5Monitor()
        monitor.module = FakeMT5()
        status = monitor.read()
        self.assertEqual(status["trade_mode"], "demo")
        self.assertEqual(status["connection_state"], "connected")
        self.assertEqual(status["account_last4"], "5412")
        self.assertEqual(status["open_positions"], 1)
        self.assertNotIn("password", status)

    def test_rejects_real_accounts(self):
        monitor = agent.MT5Monitor()
        fake = FakeMT5(trade_mode=2)
        monitor.module = fake
        status = monitor.read()
        self.assertEqual(status["trade_mode"], "unknown")
        self.assertEqual(status["connection_state"], "disconnected")
        self.assertGreater(fake.stops, 0)

    def test_terminal_loss_closes_transport(self):
        monitor = agent.MT5Monitor()
        fake = FakeMT5(connected=False)
        monitor.module = fake
        status = monitor.read()
        self.assertEqual(status["connection_state"], "disconnected")
        self.assertGreater(fake.stops, 0)

    def test_supervisor_not_configured_never_starts_bot(self):
        sup = agent.BotSupervisor([], True)
        self.assertEqual(sup.tick(demo_connected=True), "unconfigured")
        self.assertEqual(sup.tick(demo_connected=False), "unconfigured")


if __name__ == "__main__":
    unittest.main()
