#!/usr/bin/env python3
"""Opt-in secure upload of native MT5 DEMO bars to the paired read-only bridge.

Prerequisite: run/pair the existing Sentinel agent and keep a fresh heartbeat.
Only quote/bar metadata is transmitted; no account credentials or trading calls.
"""
from __future__ import annotations
import argparse
import sys
from agent import read_config, keyring_load, request_json
from export_history import extract

def main() -> None:
    p=argparse.ArgumentParser(description="Send up to 500 closed local MT5 DEMO bars")
    p.add_argument("--symbol",required=True)
    p.add_argument("--timeframe",choices=["M15","H1"],default="M15")
    p.add_argument("--bars",type=int,default=500)
    args=p.parse_args()
    if not 1<=args.bars<=500:
        raise ValueError("BAR_COUNT_MUST_BE_1_TO_500")
    cfg=read_config()
    import MetaTrader5 as mt5
    path=cfg.get("mt5_path","")
    if not (mt5.initialize(path) if path else mt5.initialize()):
        raise RuntimeError("MT5_TERMINAL_NOT_AVAILABLE")
    try:
        data=extract(mt5,args.symbol,args.timeframe,args.bars)
    finally:
        mt5.shutdown()
    if not data["candles"]:
        raise RuntimeError("NO_CLOSED_NATIVE_CANDLES")
    agent_id=cfg["agent_id"]
    token=keyring_load(agent_id)
    bypass=""
    try:
        bypass=keyring_load("vercel-bypass:"+agent_id)
    except RuntimeError:
        pass
    response=request_json(cfg["console_url"],"candles",data,
                          agent_id=agent_id,agent_token=token,bypass=bypass)
    print("Native DEMO history accepted:",response.get("accepted"),
          "source:",response.get("source"),"unverified:",response.get("unverified"))
    print("No strategy was promoted and no order was submitted.")


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print(f"{type(exc).__name__}: {str(exc)[:120]}",file=sys.stderr)
        sys.exit(1)
