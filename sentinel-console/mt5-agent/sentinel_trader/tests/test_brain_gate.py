"""No real broker credentials, market orders or network in these tests."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/"sentinel_trader").is_dir())))
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import unittest

from sentinel_trader.brain_gate import approval, TRIAL_FLAG, SOURCE
from sentinel_trader.strategy import Signal
from test_trader import settings

NOW = datetime(2026,11,18,17,0,tzinfo=timezone.utc)
SIG=Signal("EURUSD","trend_pullback",1,1700000000,.0005)


def document():
    return dict(source=SOURCE,version=1,account_login=22224444,
                account_server="Sentinel-Trade-Demo",
                issued_at=(NOW-timedelta(hours=2)).isoformat(),
                expires_at=(NOW+timedelta(days=14)).isoformat(),
                candidates=[dict(symbol="EURUSD",timeframe="M15",family="trend_pullback",
                                 candidate_id="a"*64,dataset_id="b"*64,
                                 broker_costs_verified=True,reviewed_by_operator=True,
                                 validation_trades=45,holdout_trades=24,forward_trades=26,
                                 forward_days=12,validation_expectancy_r=.16,
                                 holdout_expectancy_r=.12,forward_expectancy_r=.09,
                                 double_cost_expectancy_r=.05,robust_lower_bound_r=.01)])

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"research-approval.json"
        self.settings=replace(settings(self.tmp.name),approval_path=str(self.path))
    def check(self, doc, **overrides):
        self.path.write_text(json.dumps(doc))
        return approval(replace(self.settings,**overrides),SIG,NOW.timestamp())
    def test_no_approval_never_executes(self):
        self.assertFalse(approval(self.settings,SIG,NOW.timestamp()).allowed)
    def test_verified_approval_is_not_a_live_permission(self):
        r=self.check(document())
        self.assertTrue(r.allowed)
        self.assertEqual(r.status,"BRAIN_EVIDENCE_APPROVED_FOR_DEMO")
        self.assertEqual(r.candidate_id,"a"*64)
    def test_forged_or_mismatched_data_fails_closed(self):
        def check_mod(changes):
            d=document();d.update(changes)
            self.assertFalse(self.check(d).allowed)
        check_mod(dict(account_login=999999))
        check_mod(dict(source="GROK"))
        check_mod(dict(expires_at=(NOW-timedelta(minutes=1)).isoformat()))
        check_mod(dict(issued_at=(NOW+timedelta(minutes=1)).isoformat()))
        d=document();d["candidates"][0]["forward_trades"]=0
        self.assertFalse(self.check(d).allowed)
        d=document();d["candidates"][0]["broker_costs_verified"]=False
        self.assertFalse(self.check(d).allowed)
        d=document();d["candidates"][0]["forward_expectancy_r"]=-.1
        self.assertFalse(self.check(d).allowed)
        d=document();d["candidates"][0]["robust_lower_bound_r"]=float("nan")
        self.assertFalse(self.check(d).allowed)
        d=document();d["candidates"][0]["candidate_id"]="not_real"
        self.assertFalse(self.check(d).allowed)
    def test_do_not_cross_symbol_or_strategy(self):
        self.assertTrue(self.check(document(),allowed_login=22224444).allowed)
        self.path.write_text(json.dumps(document()))
        s=Signal("XAUUSD","trend_pullback",1,0,1)
        self.assertFalse(approval(self.settings,s,NOW.timestamp()).allowed)
        s=Signal("EURUSD","donchian_breakout",1,0,1)
        self.assertFalse(approval(self.settings,s,NOW.timestamp()).allowed)
    def test_trial_requires_second_explicit_local_flag(self):
        cfg=replace(self.settings,strategy_policy="demo_trial")
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(approval(cfg,SIG,NOW.timestamp()).allowed)
        with patch.dict(os.environ,{"SENTINEL_UNVERIFIED_DEMO_TRIAL":TRIAL_FLAG}):
            result=approval(cfg,SIG,NOW.timestamp())
            self.assertTrue(result.allowed)
            self.assertEqual(result.evidence,"NOT_VALIDATED_EDGE")

if __name__=="__main__":unittest.main()
