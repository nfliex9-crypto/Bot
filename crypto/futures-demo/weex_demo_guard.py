"""WEEX demo-only CCXT signing boundary. Not a new REST client.

CCXT 4.5.93 WEEX sandbox still uses legacy /capi/v3/sim/ routes on production.
WEEX officially moved Futures simulation to api-sim.weex.com in October 2026.
We use CCXT's native signing but route all private Futures paths to simulation.
"""
from __future__ import annotations
from urllib.parse import urlsplit
import ccxt

SIM_BASE = "https://api-sim.weex.com"


class SandboxBoundaryError(RuntimeError):
    pass


class WEEXDemoOnly(ccxt.weex):
    def __init__(self, config=None):
        config = dict(config or {})
        config["enableRateLimit"] = True
        options = dict(config.get("options") or {})
        options["defaultType"] = "swap"
        # DO NOT call obsolete CCXT set_sandbox_mode() for WEEX v4.5.93.
        options["sandboxMode"] = False
        config["options"] = options
        super().__init__(config)
        self.urls["api"]["contractPrivate"] = SIM_BASE
        self.urls["api"]["private"] = "https://disabled.invalid"

    def set_sandbox_mode(self, enable):
        raise SandboxBoundaryError("WEEX_CCXT_SANDBOX_MODE_USES_DEPRECATED_PATHS")

    def sign(self, path, api=["public"], method="GET", params={}):
        domain = api[0] if isinstance(api, (tuple, list)) else api
        if domain == "private":
            raise SandboxBoundaryError("SPOT_PRIVATE_REQUESTS_FORBIDDEN")
        if domain == "contractPrivate":
            if not path.startswith("capi/v3/") or path.startswith("capi/v3/sim/"):
                raise SandboxBoundaryError("INVALID_FUTURES_SIM_API_PATH")
            if self.urls["api"].get("contractPrivate") != SIM_BASE:
                raise SandboxBoundaryError("SIMULATION_BASE_URL_CHANGED")
        signed = super().sign(path, api, method, params)
        if domain == "contractPrivate":
            uri = urlsplit(signed["url"])
            if ((uri.scheme, uri.netloc) != ("https", "api-sim.weex.com")
                or not uri.path.startswith("/capi/v3/")):
                raise SandboxBoundaryError("PRODUCTION_ROUTING_REJECTED")
        return signed


def build_demo_client(key: str, secret: str, passphrase: str) -> WEEXDemoOnly:
    if not all((key, secret, passphrase)):
        raise SandboxBoundaryError("MISSING_DEMO_API_CREDENTIALS")
    return WEEXDemoOnly({"apiKey": key, "secret": secret, "password": passphrase})
