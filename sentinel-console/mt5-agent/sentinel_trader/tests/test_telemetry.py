import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sentinel_trader.telemetry import safe_payload

class TelemetryTests(unittest.TestCase):
    def test_only_allowlisted_read_only_fields_sent(self):
        payload=safe_payload(dict(account_last4="4444",mode="research",execution_armed=False,
            timestamp="2026-11-18T15:00:00Z",password="topsecret",
            symbols=[dict(symbol="XAUUSD",status="NO_SIGNAL",strategy="trend_pullback",
                account_login=22224444,secret="private",order_submissions=0)]))
        self.assertEqual(payload["source"],"SENTINEL_INDEPENDENT_TRADER")
        self.assertNotIn("password",str(payload))
        self.assertNotIn("topsecret",str(payload))
        self.assertNotIn("22224444",str(payload))
        self.assertEqual(payload["symbols"][0]["status"],"NO_SIGNAL")

if __name__=="__main__":unittest.main()
