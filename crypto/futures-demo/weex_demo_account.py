"""Read-only WEEX Futures *simulation* account authentication probe.

No order methods are called, no real-account host is reachable through the
configured CCXT private Futures signing boundary, no balances or API secrets
are included in CI stdout or uploaded artifacts.
"""
from __future__ import annotations

import json
import math
import os

from weex_demo_guard import build_demo_client


def validate_sim_balance(balance):
    """Check official GET /capi/v3/account/balance array, never just HTTP 200.

    A generic parsed CCXT dict (including error payloads or empty responses)
    must NOT be considered proof that simulation credentials work.
    """
    if not isinstance(balance, dict):
        raise ValueError("SIM_BALANCE_NOT_A_DICT")
    raw = balance.get("info")
    if not isinstance(raw, list) or not raw:
        raise ValueError("SIM_BALANCE_NOT_AN_ACCOUNT_ARRAY")

    valid_assets = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("SIM_BALANCE_ENTRY_INVALID")
        asset = entry.get("asset")
        if not isinstance(asset, str) or not asset:
            raise ValueError("SIM_BALANCE_ASSET_MISSING")
        try:
            amount = float(entry["balance"])
        except (TypeError, ValueError, KeyError, OverflowError) as exc:
            raise ValueError("SIM_BALANCE_AMOUNT_INVALID") from exc
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("SIM_BALANCE_AMOUNT_INVALID")
        valid_assets.add(asset)

    if not valid_assets.intersection({"SUSDT", "USDT"}):
        raise ValueError("SIM_BALANCE_NO_USDT_DENOMINATED_ASSET")
    return {"status": "SIMULATED_FUTURES_ACCOUNT_REACHABLE",
            "environment": "WEEX_FUTURES_SIM",
            "simulated_account_data_validated": True,
            "account_balance_values_redacted": True,
            "orders_placed": 0,
            "real_money_orders_enabled": False}


def probe():
    key = os.environ.get("WEEX_SIM_API_KEY", "")
    secret = os.environ.get("WEEX_SIM_API_SECRET", "")
    passphrase = os.environ.get("WEEX_SIM_API_PASSPHRASE", "")
    if not all((key, secret, passphrase)):
        return {"status": "DEMO_ACCOUNT_NOT_CONNECTED",
                "environment": "WEEX_FUTURES_SIM",
                "orders_placed": 0,
                "requires": "WEEX_SIM_API_KEY/SECRET/PASSPHRASE"}

    session = build_demo_client(key, secret, passphrase)
    try:
        # CCXT's upstream Futures balance reader, signed exclusively on
        # https://api-sim.weex.com by WEEXDemoOnly.
        balance = session.fetch_balance({"type": "swap"})
        return validate_sim_balance(balance)
    finally:
        session.close()


def main():
    try:
        result = probe()
    except Exception as exc:
        result = {"status": "DEMO_ACCOUNT_UNVERIFIED",
                  "error_type": type(exc).__name__,
                  "environment": "WEEX_FUTURES_SIM",
                  "orders_placed": 0}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "SIMULATED_FUTURES_ACCOUNT_REACHABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
