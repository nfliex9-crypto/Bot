#!/usr/bin/env python3
"""Read-only native MT5 DEMO candle export for broker-history diagnostics.

No account password, trade permissions, cloud upload, or order calls.
Run on the Windows computer with MetaTrader5 installed and a demo terminal open.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

TF_SECONDS = {"M15": 900, "H1": 3600}
TF_API = {"M15": "TIMEFRAME_M15", "H1": "TIMEFRAME_H1"}


def extract(mt5, symbol: str, timeframe: str, count: int = 1500, now: float | None = None) -> dict:
    if not isinstance(symbol, str) or not (2 <= len(symbol) <= 24) or not all(
        char.isalnum() or char in "._#-" for char in symbol
    ):
        raise ValueError("INVALID_NATIVE_SYMBOL")
    if timeframe not in TF_SECONDS or not 1 <= count <= 5000:
        raise ValueError("INVALID_NATIVE_HISTORY_REQUEST")
    account = mt5.account_info()
    terminal = mt5.terminal_info()
    if not account or not terminal or not getattr(terminal, "connected", False):
        raise RuntimeError("MT5_NOT_CONNECTED")
    if int(account.trade_mode) != int(mt5.ACCOUNT_TRADE_MODE_DEMO):
        raise RuntimeError("DEMO_ACCOUNT_REQUIRED")
    details = mt5.symbol_info(symbol)
    if details is None or not mt5.symbol_select(symbol, True):
        raise RuntimeError("SYMBOL_NOT_AVAILABLE")
    point = float(getattr(details, "point", 0))
    if not (point > 0):
        raise RuntimeError("SYMBOL_POINT_MISSING")
    # Start position 1 excludes the still-forming bar at position 0.
    rows = mt5.copy_rates_from_pos(symbol, getattr(mt5, TF_API[timeframe]), 1, count)
    if rows is None:
        raise RuntimeError("MT5_HISTORY_NOT_AVAILABLE")
    utc_now = time.time() if now is None else now
    parsed = []
    for row in rows:
        stamp = int(row["time"])
        if stamp < 0 or stamp + TF_SECONDS[timeframe] > utc_now:
            continue
        raw_spread = int(row["spread"])
        spread = round(raw_spread * point, 12) if raw_spread > 0 else None
        parsed.append({
            "timestamp": stamp, "open": float(row["open"]), "high": float(row["high"]),
            "low": float(row["low"]), "close": float(row["close"]),
            "spread": spread, "tickVolume": int(row["tick_volume"])
        })
    parsed.sort(key=lambda row: row["timestamp"])
    if any(x["timestamp"] >= y["timestamp"] for x, y in zip(parsed, parsed[1:])):
        raise RuntimeError("DUPLICATED_NATIVE_TIMESTAMPS")
    return {
        "source": "LOCAL_MT5_DEMO_TERMINAL",
        "trade_mode": "demo",
        "symbol": symbol, "timeframe": timeframe,
        "broker_server": str(account.server)[:80],
        "account_last4": str(account.login)[-4:],
        "point": point,
        "spread_unit": "absolute_price",
        "requested_bars": count, "returned_closed_bars": len(parsed),
        "spread_observed_bars": sum(x["spread"] is not None for x in parsed),
        "coverage": "LOCAL_EXPORT_NOT_YET_BROKER_CROSSCHECKED",
        "exported_at_utc": datetime.fromtimestamp(utc_now, timezone.utc).isoformat(),
        "candles": parsed, "orders_executed": 0
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export genuine MT5 DEMO closed candles, read-only")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="M15", choices=tuple(TF_SECONDS))
    parser.add_argument("--bars", type=int, default=1500)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError("MT5_INITIALIZE_FAILED")
    try:
        dataset = extract(mt5, args.symbol, args.timeframe, args.bars)
    finally:
        mt5.shutdown()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite existing research export")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(dataset, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Exported {dataset['returned_closed_bars']} closed DEMO bars to {args.out}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
