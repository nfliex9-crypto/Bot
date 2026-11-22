"""Demo-only WEEX futures account probe. No orders are ever placed by this file.

Credentials are read from environment; never print keys or private response bodies.
Runs only on official WEEX simulation endpoint via weex_demo_guard.
"""
from __future__ import annotations
import json
import os
from weex_demo_guard import build_demo_client, SandboxBoundaryError

def probe():
    key=os.environ.get("WEEX_SIM_API_KEY","")
    secret=os.environ.get("WEEX_SIM_API_SECRET","")
    passphrase=os.environ.get("WEEX_SIM_API_PASSPHRASE","")
    if not all((key,secret,passphrase)):
        return {"status":"DEMO_ACCOUNT_NOT_CONNECTED","environment":"WEEX_FUTURES_SIM",
                "orders_placed":0,"requires":"WEEX_SIM_API_KEY/SECRET/PASSPHRASE"}
    session=build_demo_client(key,secret,passphrase)
    try:
        balance=session.fetch_balance({"type":"swap"})
        return {"status":"SIMULATED_FUTURES_ACCOUNT_REACHABLE",
                "environment":"WEEX_FUTURES_SIM",
                "balance_type":type(balance).__name__,
                "orders_placed":0,
                "real_money_orders_enabled":False}
    finally:
        session.close()

def main():
    try:
        result=probe()
    except Exception as e:
        result={"status":"DEMO_ACCOUNT_UNVERIFIED","error_type":type(e).__name__,
                "environment":"WEEX_FUTURES_SIM","orders_placed":0}
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="SIMULATED_FUTURES_ACCOUNT_REACHABLE" else 1

if __name__=="__main__":
    raise SystemExit(main())
