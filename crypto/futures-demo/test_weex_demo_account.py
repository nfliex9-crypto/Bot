"""Offline-only tests of WEEX read-only simulated account validation."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from weex_demo_account import validate_sim_balance, probe


class AccountValidation(unittest.TestCase):
    def test_valid_sim_susdt(self):
        report = validate_sim_balance({"info": [
            {"asset": "SUSDT", "balance": "50000.00", "availableBalance": "50000.00"}
        ]})
        self.assertEqual(report["status"], "SIMULATED_FUTURES_ACCOUNT_REACHABLE")
        self.assertEqual(report["orders_placed"], 0)
        self.assertNotIn("balance", report)

    def test_accept_zero_balance_without_claiming_funds(self):
        report = validate_sim_balance({"info": [{"asset": "USDT", "balance": "0"}]})
        self.assertTrue(report["account_balance_values_redacted"])

    def test_reject_dict_error_disguised_as_http_200(self):
        with self.assertRaisesRegex(ValueError, "NOT_AN_ACCOUNT_ARRAY"):
            validate_sim_balance({"info": {"code": -1052, "msg": "permission denied"}})

    def test_reject_empty_account_response(self):
        with self.assertRaises(ValueError):
            validate_sim_balance({"info": []})

    def test_reject_nonfinite_amount(self):
        for amount in ("nan", "inf", "-1", "bad"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    validate_sim_balance({"info": [{"asset": "SUSDT", "balance": amount}]})

    def test_reject_wrong_asset(self):
        with self.assertRaises(ValueError):
            validate_sim_balance({"info": [{"asset": "BTC", "balance": "2"}]})

    def test_reject_missing_asset(self):
        with self.assertRaises(ValueError):
            validate_sim_balance({"info": [{"balance": "20"}]})

    def test_reject_wrong_outer_type(self):
        with self.assertRaises(ValueError):
            validate_sim_balance([{"asset": "SUSDT", "balance": "10"}])

    def test_missing_secrets_must_not_call_upstream(self):
        empty = {
            "WEEX_SIM_API_KEY": "",
            "WEEX_SIM_API_SECRET": "",
            "WEEX_SIM_API_PASSPHRASE": "",
        }
        with patch.dict(os.environ, empty), patch(
            "weex_demo_account.build_demo_client"
        ) as fake:
            result = probe()
        self.assertEqual(result["status"], "DEMO_ACCOUNT_NOT_CONNECTED")
        fake.assert_not_called()

    def test_only_balance_read_invoked_with_sim_guard(self):
        class FakeExchange:
            def __init__(self):
                self.params = None
                self.closed = False

            def fetch_balance(self, params):
                self.params = params
                return {"info": [{"asset": "SUSDT", "balance": "5"}]}

            def close(self):
                self.closed = True

        fake = FakeExchange()
        env = {
            "WEEX_SIM_API_KEY": "DUMMY_TESTONLY_KEY",
            "WEEX_SIM_API_SECRET": "DUMMY_TESTONLY_SECRET",
            "WEEX_SIM_API_PASSPHRASE": "DUMMY_TESTONLY_PASSPHRASE",
        }
        with patch.dict(os.environ, env), patch(
            "weex_demo_account.build_demo_client", return_value=fake
        ) as builder:
            result = probe()
        self.assertEqual(result["status"], "SIMULATED_FUTURES_ACCOUNT_REACHABLE")
        self.assertTrue(fake.closed)
        self.assertEqual(fake.params, {"type": "swap"})
        builder.assert_called_once()


if __name__ == "__main__":
    unittest.main()
