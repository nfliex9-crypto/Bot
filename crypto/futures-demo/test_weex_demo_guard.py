"""No-network tests that assert official WEEX simulation REST routing."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from weex_demo_guard import WEEXDemoOnly, SandboxBoundaryError, SIM_BASE

class DemoOnlySigningTests(unittest.TestCase):
    def setUp(self):
        self.exchange=WEEXDemoOnly({
            "apiKey":"DUMMY_KEY_NOT_REAL",
            "secret":"DUMMY_SECRET_NOT_REAL",
            "password":"DUMMY_PASSPHRASE_NOT_REAL",
        })
        self.addCleanup(self.exchange.close)

    def test_balance_api_uses_sim_only(self):
        signed=self.exchange.sign("capi/v3/account/balance",["contractPrivate"],"GET",{})
        self.assertTrue(signed["url"].startswith(SIM_BASE+"/capi/v3/"))

    def test_demo_order_api_uses_sim_only(self):
        signed=self.exchange.sign("capi/v3/order",["contractPrivate"],"POST",{
            "symbol":"BTCUSDT","side":"BUY","type":"LIMIT","quantity":"0.001","price":"1000"
        })
        self.assertTrue(signed["url"].startswith(SIM_BASE+"/capi/v3/order"))
        self.assertEqual(signed["method"],"POST")

    def test_spot_private_is_forbidden(self):
        with self.assertRaises(SandboxBoundaryError):
            self.exchange.sign("api/v3/order",["private"],"POST",{})

    def test_old_sim_path_is_forbidden(self):
        with self.assertRaises(SandboxBoundaryError):
            self.exchange.sign("capi/v3/sim/order",["contractPrivate"],"POST",{})

    def test_production_url_tampering_rejected(self):
        self.exchange.urls["api"]["contractPrivate"]="https://api-contract.weex.com"
        with self.assertRaises(SandboxBoundaryError):
            self.exchange.sign("capi/v3/order",["contractPrivate"],"POST",{})

    def test_ccxt_old_sandbox_mode_is_forbidden(self):
        with self.assertRaises(SandboxBoundaryError):
            self.exchange.set_sandbox_mode(True)

if __name__=="__main__":
    unittest.main()
