"""Offline MT5 mock: no accounts, real network or orders involved."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as S
import os
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sentinel_trader.config import Settings
from sentinel_trader.journal import Journal
from sentinel_trader.strategy import Signal, decide, ema, atr
from sentinel_trader.trader import Trader, ACTIVATION, floor_volume, key_for


def settings(folder,**overrides):
    d=dict(mode="research",allowed_login=22224444,allowed_server="Sentinel-Trade-Demo",
      blocked_logins=(563722,),symbols=("EURUSD",),magic=82618011,
      risk_per_trade_pct=.25,max_daily_drawdown_pct=1.5,max_positions=2,
      max_lots=.2,max_spread_bps=8.,max_tick_age_seconds=15,deviation_points=15,
      poll_seconds=20,journal_path=str(Path(folder)/"trades.db"),status_path=str(Path(folder)/"status.json"))
    return Settings(**{**d,**overrides})

class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO=0
    SYMBOL_TRADE_MODE_FULL=4
    TIMEFRAME_M15=15
    TIMEFRAME_H1=60
    TRADE_ACTION_DEAL=1
    ORDER_TYPE_BUY=0
    ORDER_TYPE_SELL=1
    ORDER_FILLING_IOC=1
    ORDER_FILLING_FOK=0
    ORDER_TIME_GTC=0
    TRADE_RETCODE_DONE=10009
    def __init__(self,now):
        self.now=now
        self.account=S(login=22224444,server="Sentinel-Trade-Demo",trade_mode=0,
                       equity=5000.,trade_allowed=True)
        self.terminal=S(connected=True,trade_allowed=True)
        self.positions=[];self.orders=[];self.sent=[];self.checks=[]
        self.response=S(retcode=10009,order=9001)
        self.profit_result=-100.0
        self.history=[]
        self.info=S(volume_min=.01,volume_max=100.,volume_step=.01,trade_mode=4,
                    digits=5,point=.00001,trade_stops_level=0,filling_mode=3)
        self.tick=S(bid=1.1,ask=1.10002,time_msc=int(now*1000))
        self.initialized=False;self.closed=False
    def initialize(self):self.initialized=True;return True
    def shutdown(self):self.closed=True
    def account_info(self):return self.account
    def terminal_info(self):return self.terminal
    def positions_get(self):return self.positions
    def orders_get(self):return self.orders
    def history_deals_get(self,a,b):return self.history
    def symbol_select(self,s,b):return True
    def symbol_info(self,s):return self.info
    def symbol_info_tick(self,s):return self.tick
    def order_calc_profit(self,kind,symbol,volume,entry,stop):return self.profit_result*volume
    def order_check(self,request):self.checks.append(request);return S(retcode=0)
    def order_send(self,request):self.sent.append(request);return self.response
    def copy_rates_from_pos(self,symbol,tf,pos,count):return None

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=1795005600.0
        self.mt5=FakeMT5(self.now)
        self.journal=Journal(Path(self.tmp.name)/"ledger.db")
        self.addCleanup(self.journal.close)
    def build(self,**kw):
        t=Trader(settings(self.tmp.name,**kw),self.mt5,self.journal,clock=lambda:self.now)
        t.connect()
        t.observe=lambda _:Signal("EURUSD","trend_pullback",1,int(self.now//900*900-900),.001)
        self.addCleanup(t.disconnect)
        return t
    def test_account_hard_stop_refuses_grok_and_real(self):
        with self.assertRaises(ValueError):settings(self.tmp.name,allowed_login=563722).validate()
        self.mt5.account.login=563722
        with self.assertRaisesRegex(RuntimeError,"SEPARATE_VERIFIED"):
            self.build()
        self.mt5.account.login=22224444;self.mt5.account.trade_mode=2
        with self.assertRaisesRegex(RuntimeError,"SEPARATE_VERIFIED"):
            self.build()
    def test_research_mode_never_calls_order_send_even_with_signal(self):
        t=self.build()
        state=t.step("EURUSD")
        self.assertEqual(state["status"],"RESEARCH_SIGNAL")
        self.assertEqual(self.mt5.sent,[])
        self.assertEqual(self.mt5.checks,[])
    def test_demo_mode_requires_explicit_activation(self):
        old=os.environ.pop("SENTINEL_ENABLE_DEMO_TRADING",None)
        try:
            t=self.build(mode="demo_execution")
            self.assertEqual(t.step("EURUSD")["status"],"RESEARCH_SIGNAL")
            self.assertEqual(self.mt5.sent,[])
        finally:
            if old is not None:os.environ["SENTINEL_ENABLE_DEMO_TRADING"]=old
    def test_demo_sends_single_bound_order_then_refuses_duplicate(self):
        old=os.environ.get("SENTINEL_ENABLE_DEMO_TRADING")
        os.environ["SENTINEL_ENABLE_DEMO_TRADING"]=ACTIVATION
        try:
            t=self.build(mode="demo_execution")
            first=t.step("EURUSD")
            self.assertEqual(first["status"],"BROKER_ACK_AWAITING_RECONCILIATION")
            self.assertEqual(len(self.mt5.sent),1)
            req=self.mt5.sent[0]
            self.assertGreater(req["sl"],0);self.assertGreater(req["tp"],req["price"])
            self.assertEqual(req["magic"],82618011)
            self.assertEqual(req["volume"],.12)
            self.assertEqual(t.step("EURUSD")["status"],"UNRESOLVED_BROKER_INTENT")
            self.assertEqual(len(self.mt5.sent),1)
            self.mt5.positions=[S(magic=82618011,symbol="EURUSD",comment=req["comment"],ticket=9001)]
            self.assertEqual(t.step("EURUSD")["status"],"POSITION_CAP_OR_SYMBOL_BUSY")
            self.mt5.positions=[]
            self.assertEqual(t.step("EURUSD")["status"],"DUPLICATE_SIGNAL_IDEMPOTENT_SKIP")
            self.assertEqual(len(self.mt5.sent),1)
        finally:
            if old is None:os.environ.pop("SENTINEL_ENABLE_DEMO_TRADING",None)
            else:os.environ["SENTINEL_ENABLE_DEMO_TRADING"]=old
    def test_unknown_response_blocks_future_submissions_even_after_restart(self):
        old=os.environ.get("SENTINEL_ENABLE_DEMO_TRADING")
        os.environ["SENTINEL_ENABLE_DEMO_TRADING"]=ACTIVATION
        try:
            self.mt5.response=None
            t=self.build(mode="demo_execution")
            self.assertEqual(t.step("EURUSD")["status"],"BROKER_OUTCOME_UNKNOWN")
            self.assertEqual(len(self.mt5.sent),1)
            new=Trader(t.cfg,self.mt5,self.journal,clock=lambda:self.now)
            new.connect();new.observe=t.observe
            self.addCleanup(new.disconnect)
            self.assertEqual(new.step("EURUSD")["status"],"UNRESOLVED_BROKER_INTENT")
            self.assertEqual(len(self.mt5.sent),1)
        finally:
            if old is None:os.environ.pop("SENTINEL_ENABLE_DEMO_TRADING",None)
            else:os.environ["SENTINEL_ENABLE_DEMO_TRADING"]=old
    def test_foreign_positions_or_orders_block(self):
        t=self.build()
        self.mt5.positions=[S(magic=23456,symbol="XAUUSD")]
        self.assertEqual(t.step("EURUSD")["status"],"FOREIGN_POSITION_OR_PENDING_ORDER")
        self.mt5.positions=[];self.mt5.orders=[S(ticket=5)]
        self.assertEqual(t.step("EURUSD")["status"],"FOREIGN_POSITION_OR_PENDING_ORDER")
    def test_daily_loss_locks_trading_before_signal(self):
        t=self.build()
        self.assertEqual(t.step("EURUSD")["status"],"RESEARCH_SIGNAL")
        self.mt5.account.equity=4900.
        self.assertEqual(t.step("EURUSD")["status"],"DAILY_DRAWDOWN_LOCK")
    def test_spread_stop_lot_validation(self):
        t=self.build(mode="demo_execution")
        info=self.mt5.info;tick=self.mt5.tick
        signal=t.observe("EURUSD")
        req,reason=t._request(signal,self.mt5.account,tick,info)
        self.assertEqual(reason,"READY")
        self.assertAlmostEqual(req["volume"],.12)
        tick.ask=1.101
        self.assertEqual(t._request(signal,self.mt5.account,tick,info)[1],"SPREAD_TOO_WIDE")
        tick.ask=1.10002;tick.time_msc=int((self.now-120)*1000)
        self.assertEqual(t._request(signal,self.mt5.account,tick,info)[1],"BAD_OR_STALE_QUOTE")
        self.assertAlmostEqual(floor_volume(.39,.05,1.,.25),.30)
        self.assertEqual(floor_volume(.01,.05,1.,.25),0)
    def test_minimum_lot_refused_if_risk_budget_insufficient(self):
        t=self.build(mode="demo_execution")
        self.mt5.profit_result=-100000.
        req,reason=t._request(t.observe("EURUSD"),self.mt5.account,self.mt5.tick,self.mt5.info)
        self.assertIsNone(req)
        self.assertEqual(reason,"NATIVE_RISK_TOO_SMALL_FOR_MIN_LOT")
    def test_broker_account_swap_during_cycle_is_refused(self):
        t=self.build(mode="demo_execution")
        self.mt5.account.login=33334444
        self.assertEqual(t.step("EURUSD")["status"],"DEMO_CONNECTION_LOST")
        self.assertEqual(self.mt5.sent,[])
    def test_status_file_has_no_secret_or_mt5_account_number(self):
        t=self.build()
        x=t.cycle()
        blob=Path(t.cfg.status_path).read_text()
        self.assertEqual(x["account_last4"],"4444")
        self.assertNotIn("22224444",blob)
        self.assertNotIn("password",blob)
        self.assertTrue(x["not_grok"])

if __name__=="__main__":unittest.main()

class StrategyAndResilience(unittest.TestCase):
    def test_closed_bar_trend_reclaim_long_and_short(self):
        base=1_700_000_000
        for side in (1,-1):
            prices=[100 + side*i*.1 for i in range(125)]
            prices[-2]-=side*2
            prices[-1]+=side*.3
            m15=[dict(time=base+i*900,open=x,high=x+.2,low=x-.2,close=x) for i,x in enumerate(prices)]
            h1=[dict(time=base+i*3600,open=100+side*i*.15,high=100+side*i*.15+.2,
                     low=100+side*i*.15-.2,close=100+side*i*.15) for i in range(100)]
            signal=decide("TEST",m15,h1)
            self.assertIsNotNone(signal)
            self.assertEqual(signal.side,side)
            self.assertEqual(signal.family,"trend_pullback")
    def test_duplicate_candles_must_never_produce_signal(self):
        bars=[dict(time=i*900,open=1,high=2,low=.5,close=1.5) for i in range(120)]
        hour=[dict(time=i*3600,open=1,high=2,low=.5,close=1.5) for i in range(100)]
        bars[-1]["time"]=bars[-2]["time"]
        with self.assertRaisesRegex(ValueError,"UNSORTED_OR_DUPLICATE"):
            decide("TEST",bars,hour)
    def test_reserved_account_even_if_user_deletes_blocked_list(self):
        with self.assertRaisesRegex(ValueError,"EXCLUSIVE_SEPARATE"):
            settings("/tmp",allowed_login=563722,blocked_logins=()).validate()
    def test_config_file_rejects_unbound_demo_account(self):
        import json
        with TemporaryDirectory() as folder:
            p=Path(folder)/"config.json"
            from sentinel_trader.config import Settings as Config
            p.write_text(json.dumps(dict(mode="research",allowed_login=0,allowed_server="",symbols=["EURUSD"],
                magic=82618011,risk_per_trade_pct=.25,max_daily_drawdown_pct=1.5,max_positions=2,
                max_lots=.2,max_spread_bps=8.,max_tick_age_seconds=15,deviation_points=15,
                poll_seconds=20,journal_path="state/journal.db",status_path="state/status.json")))
            with self.assertRaisesRegex(ValueError,"EXCLUSIVE_SEPARATE"):
                Config.from_file(p)
