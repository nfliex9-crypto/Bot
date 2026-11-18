"""Optional owner-dashboard telemetry from the paired Windows DEMO agent.

The cloud cannot send orders, lot changes, strategy instructions, or passwords.
All trading decisions stay on the isolated Windows terminal.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse


def safe_payload(state: dict) -> dict:
    symbols=[]
    for s in state.get("symbols",[])[:8]:
        if not isinstance(s,dict):continue
        symbols.append({k:s[k] for k in ("symbol","status","strategy","side","closed_bar","order_submissions",
                             "brain_status","research_evidence","orderbook_status","book_samples",
                             "book_imbalance","book_persistent_side")
                        if k in s and type(s[k]) in (str,int,float)})
    return {"source":"SENTINEL_INDEPENDENT_TRADER", "account_last4":str(state.get("account_last4","")),
            "mode":state.get("mode"),"execution_armed":state.get("execution_armed") is True,
            "strategy_policy":state.get("strategy_policy"),"orderbook_mode":state.get("orderbook_mode"),
            "timestamp":state.get("timestamp"),"symbols":symbols}


def upload(state: dict, *, agent_root: Path | None = None) -> dict:
    # Uses the existing local Sentinel pairing only. Never stores tokens in project files.
    from importlib.util import spec_from_file_location,module_from_spec
    path=Path(__file__).resolve().parents[1]/"agent.py"
    if not path.is_file():
        raise RuntimeError("SENTINEL_PAIRED_AGENT_NOT_INSTALLED")
    spec=spec_from_file_location("sentinel_agent_read_only",path)
    agent=module_from_spec(spec)
    spec.loader.exec_module(agent)
    cfg=agent.read_config()
    ident=cfg["agent_id"]
    secret=agent.keyring_load(ident)
    bypass=""
    try:bypass=agent.keyring_load("vercel-bypass:"+ident)
    except RuntimeError:pass
    url=str(cfg.get("console_url",""))
    if not url.startswith("https://sentinel-mt5-bridge") or not url.endswith(".vercel.app"):
        raise RuntimeError("UNKNOWN_SENTINEL_BRIDGE_ORIGIN")
    return agent.request_json(url,"trader-status",safe_payload(state),
                              agent_id=ident,agent_token=secret,bypass=bypass)
