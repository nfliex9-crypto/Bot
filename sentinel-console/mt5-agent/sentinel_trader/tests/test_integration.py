"""Proof of Sentinel Brain/DOM execution boundaries with a fully mocked MT5."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/"sentinel_trader").is_dir())))
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory
from types import SimpleNamespace as S
import unittest

from sentinel_trader.brain_gate import TRIAL_FLAG
from sentinel_trader.trader import Trader, ACTIVATION
from sentinel_trader.strategy import Signal
from sentinel_trader.journal import Journal
from test_trader import FakeMT5,settings

class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1795005600.0
        self.mt5=FakeMT5(self.now)
        self.journal=Journal(Path(self.tmp.name)/"test-intents.db")
        self.addCleanup(self.journal.close)
    def make(self,**options):
        t=Trader(settings(self.tmp.name,**options),self.mt5,self.journal,clock=lambda:self.now)
        t.connect();self.addCleanup(t.disconnect)
        t.observe=lambda _:Signal("EURUSD","trend_pullback",1,int(self.now//900*900-900),.001)
        return t
    def test_default_policy_blocks_even_with_demo_activation(self):
        with patch.dict("os.environ",{"SENTINEL_ENABLE_DEMO_TRADING":ACTIVATION},clear=True):
            t=self.make(mode="demo_execution",orderbook_mode="off")
            x=t.step("EURUSD")
            self.assertEqual(x["status"],"BRAIN_EVIDENCE_NOT_APPROVED")
            self.assertEqual(x["brain_status"],"NO_APPROVED_SENTINEL_BRAIN_CANDIDATE")
            self.assertEqual(self.mt5.sent,[])
    def test_second_consent_needed_for_explicit_unverified_demo_trial(self):
        t=self.make(mode="demo_execution",strategy_policy="demo_trial",orderbook_mode="off")
        with patch.dict("os.environ",{"SENTINEL_ENABLE_DEMO_TRADING":ACTIVATION},clear=True):
            self.assertEqual(t.step("EURUSD")["status"],"BRAIN_EVIDENCE_NOT_APPROVED")
            self.assertEqual(self.mt5.sent,[])
        with patch.dict("os.environ",{"SENTINEL_ENABLE_DEMO_TRADING":ACTIVATION,
                                      "SENTINEL_UNVERIFIED_DEMO_TRIAL":TRIAL_FLAG},clear=True):
            self.assertEqual(t.step("EURUSD")["status"],"BROKER_ACK_AWAITING_RECONCILIATION")
            self.assertEqual(len(self.mt5.sent),1)
    def test_dom_confirmation_blocks_on_missing_broker_book(self):
        t=self.make(mode="demo_execution",strategy_policy="demo_trial",orderbook_mode="confirm")
        with patch.dict("os.environ",{"SENTINEL_ENABLE_DEMO_TRADING":ACTIVATION,
                                      "SENTINEL_UNVERIFIED_DEMO_TRIAL":TRIAL_FLAG},clear=True):
            out=t.step("EURUSD")
            self.assertEqual(out["status"],"BROKER_DOM_CONFIRMATION_MISSING")
            self.assertEqual(out["orderbook_status"],"BROKER_DOM_NOT_OFFERED")
            self.assertEqual(self.mt5.sent,[])
    def test_broker_book_is_recorded_as_diagnostic_in_research(self):
        self.mt5.BOOK_TYPE_BUY=1;self.mt5.BOOK_TYPE_SELL=2
        self.mt5.market_book_add=lambda symbol:True
        self.mt5.market_book_get=lambda symbol:[S(type=1,price=1.10000,volume_dbl=3),
                                                 S(type=2,price=1.10002,volume_dbl=1)]
        self.mt5.market_book_release=lambda symbol:None
        t=self.make()
        x=t.step("EURUSD")
        self.assertEqual(x["status"],"RESEARCH_SIGNAL")
        self.assertEqual(x["orderbook_status"],"BROKER_DOM_OBSERVED")
        self.assertAlmostEqual(x["book_imbalance"],.5)
        self.assertEqual(self.mt5.sent,[])
    def test_stale_ohlc_signal_no_order_even_with_trial_override(self):
        t=self.make(mode="demo_execution",strategy_policy="demo_trial",orderbook_mode="off",max_signal_age_seconds=90)
        with patch.dict("os.environ",{"SENTINEL_ENABLE_DEMO_TRADING":ACTIVATION,
                                      "SENTINEL_UNVERIFIED_DEMO_TRIAL":TRIAL_FLAG},clear=True):
            self.assertEqual(t.step("EURUSD")["status"],"SIGNAL_TOO_OLD_FOR_ENTRY")
            self.assertEqual(self.mt5.sent,[])

if __name__=="__main__":unittest.main()
