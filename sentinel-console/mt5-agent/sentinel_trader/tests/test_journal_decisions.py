from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(next(p for p in Path(__file__).resolve().parents if (p/"sentinel_trader").is_dir())))
from tempfile import TemporaryDirectory
import unittest
from sentinel_trader.journal import Journal

class DecisionJournalTests(unittest.TestCase):
    def test_observations_persist_without_being_orders_or_fake_trades(self):
        with TemporaryDirectory() as folder:
            file=Path(folder)/"research.sqlite"
            a=Journal(file)
            a.record_decision("sig1",123,"XAUUSD","trend_pullback",1,1700,
                              "NO_APPROVED_SENTINEL_BRAIN_CANDIDATE","BROKER_DOM_EMPTY",
                              "BRAIN_EVIDENCE_NOT_APPROVED")
            a.record_decision("sig1",123,"XAUUSD","trend_pullback",1,1700,
                              "BRAIN_EVIDENCE_APPROVED_FOR_DEMO","BROKER_DOM_OBSERVED",
                              "RESEARCH_SIGNAL")
            a.close()
            b=Journal(file)
            rows=b.recent_decisions(123)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["status"],"RESEARCH_SIGNAL")
            self.assertEqual(b.all_intents(),[])
            self.assertEqual(b.recent_decisions(456),[])
            b.close()
    def test_invalid_side_does_not_create_decision(self):
        with TemporaryDirectory() as folder:
            j=Journal(Path(folder)/"r.sqlite")
            with self.assertRaises(ValueError):
                j.record_decision("sig",123,"BTCUSD","breakout",0,0,"no","no","no")
            self.assertEqual(j.recent_decisions(123),[])
            j.close()

if __name__=="__main__":unittest.main()
