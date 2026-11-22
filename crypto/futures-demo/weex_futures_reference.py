"""Public WEEX USDT perpetual reference quotes using CCXT 4.5.93.

Last trade, Mark, Index, Funding and Open Interest are not interchangeable.
No credentials, manual price substitute, spot feed, order placement or simulation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import time

from weex_futures_feed import PAIRS, verify_swap


class ReferenceRejected(ValueError):
    pass


def finite_value(value, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReferenceRejected("MISSING_NUMERIC_REFERENCE") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        raise ReferenceRejected("INVALID_NUMERIC_REFERENCE")
    return number


def recent_millis(value, now_ms: int, max_age_ms: int = 180000,
                  source: str = "unknown") -> int:
    try:
        ts = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ReferenceRejected(f"{source}_TIMESTAMP_MISSING") from exc
    if ts < 1_600_000_000_000 or ts > now_ms + 15000 or now_ms - ts > max_age_ms:
        raise ReferenceRejected(f"{source}_STALE_OR_FUTURE_REFERENCE_TIMESTAMP_age_ms_{now_ms-ts}")
    return ts


def recent_executed_trade(symbol: str, trades: list, now_ms: int) -> dict:
    """Last = a verified actual WEEX *perpetual contract* trade, not 24h ticker."""
    if not isinstance(trades, list) or not trades:
        raise ReferenceRejected("NO_PUBLIC_FUTURES_EXECUTED_TRADES")
    candidate = None
    for trade in trades:
        if not isinstance(trade, dict):
            raise ReferenceRejected("INVALID_PUBLIC_TRADE_STRUCTURE")
        if trade.get("symbol") != symbol:
            raise ReferenceRejected("FOREIGN_MARKET_TRADE")
        if trade.get("side") not in ("buy", "sell"):
            raise ReferenceRejected("INVALID_TRADE_SIDE")
        finite_value(trade.get("price"), positive=True)
        finite_value(trade.get("amount"), positive=True)
        try:
            ts = int(trade.get("timestamp"))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ReferenceRejected("MISSING_TRADE_TIMESTAMP") from exc
        if trade.get("id") is None:
            raise ReferenceRejected("MISSING_EXECUTED_TRADE_ID")
        if candidate is None or ts > int(candidate["timestamp"]):
            candidate = trade
    recent_millis(candidate["timestamp"], now_ms, max_age_ms=45000,
                  source="last_executed_trade")
    return {
        "symbol": symbol,
        "last": candidate["price"], "timestamp": candidate["timestamp"],
        "trade_id": str(candidate["id"]),
    }


def build_reference(symbol: str, ticker: dict, funding: dict, interest: dict,
                    now_ms: int) -> dict:
    if symbol not in PAIRS:
        raise ReferenceRejected("NOT_APPROVED_USDT_PERPETUAL")
    if any(not isinstance(row, dict) or row.get("symbol") != symbol
           for row in (ticker, funding, interest)):
        raise ReferenceRejected("CROSS_MARKET_REFERENCE_REJECTED")

    last = finite_value(ticker.get("last"), positive=True)
    mark = finite_value(funding.get("markPrice"), positive=True)
    index = finite_value(funding.get("indexPrice"), positive=True)
    rate = finite_value(funding.get("fundingRate"))
    oi = finite_value(interest.get("openInterestAmount"), positive=True)
    predicted = funding.get("nextFundingRate")
    next_rate = finite_value(predicted) if predicted is not None else None
    funding_ts = recent_millis(funding.get("timestamp"), now_ms, source="funding")
    oi_ts = recent_millis(interest.get("timestamp"), now_ms, source="open_interest")
    # Current funding rate is not identical to NEXT settlement's forecast.
    next_funding_at = funding.get("nextFundingTimestamp")
    next_funding_ms = None
    if next_funding_at is not None:
        next_funding_ms = int(next_funding_at)
        if next_funding_ms < funding_ts - 86400000:
            raise ReferenceRejected("INVALID_NEXT_FUNDING_TIME")
    ticker_ts = recent_millis(
        ticker.get("timestamp"), now_ms,
        max_age_ms=45000, source="last_executed_trade")

    return {
        "status": "VERIFIED_PUBLIC_PERPETUAL_REFERENCE",
        "venue": "WEEX", "symbol": symbol, "market": "USDT_LINEAR_PERPETUAL",
        "source": "ccxt_4.5.93_weex_public_futures_rest",
        "last_futures_price": last,
        "mark_price": mark,
        "index_price": index,
        "last_funding_rate": rate,
        "forecast_funding_rate": next_rate,
        "next_funding_at_ms": next_funding_ms,
        "open_interest_contract_units": oi,
        "last_vs_mark_bps": round(10000 * (last / mark - 1), 5),
        "mark_vs_index_bps": round(10000 * (mark / index - 1), 5),
        "last_executed_trade_exchange_time_ms": ticker_ts,
        "last_executed_trade_id": ticker.get("trade_id"),
        "last_price_origin": "ccxt_weex_public_futures_recent_executed_trades",
        "funding_exchange_time_ms": funding_ts,
        "open_interest_exchange_time_ms": oi_ts,
        "observed_at_ms": now_ms,
        "orders_enabled": False,
        "uses_spot_price": False,
        "synthetic_data": False,
    }


async def snapshot(symbol: str) -> dict:
    import ccxt.async_support as ccxt
    exchange = ccxt.weex({"enableRateLimit": True, "options": {"defaultType": "swap"}})
    try:
        await asyncio.wait_for(exchange.load_markets(), timeout=25)
        verify_swap(exchange.market(symbol), symbol)
        rates, interest, trades = await asyncio.wait_for(
            asyncio.gather(
                exchange.fetch_funding_rates([symbol]),
                exchange.fetch_open_interest(symbol),
                exchange.fetch_trades(symbol, limit=10),
            ), timeout=30,
        )
        rate = rates.get(symbol) if isinstance(rates, dict) else None
        if not isinstance(rate, dict):
            raise ReferenceRejected("MISSING_MARK_INDEX_FUNDING")
        now_ms = int(time.time() * 1000)
        last_execution = recent_executed_trade(symbol, trades, now_ms)
        return build_reference(symbol, last_execution, rate, interest, now_ms)
    finally:
        await exchange.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Current public WEEX perpetual index/mark/funding/OI")
    parser.add_argument("--symbol", choices=PAIRS, default=PAIRS[0])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    try:
        result = asyncio.run(snapshot(args.symbol))
        code = 0
    except Exception as exc:
        result = {
            "status": "FUTURES_REFERENCE_NOT_VERIFIED", "venue": "WEEX",
            "symbol": args.symbol, "error_type": type(exc).__name__,
            "reason": str(exc) if isinstance(exc, ReferenceRejected) else "UPSTREAM_REQUEST_FAILED",
            "orders_enabled": False, "synthetic_data": False,
        }
        code = 1
    line = json.dumps(result, sort_keys=True, separators=(",", ":"))
    print(line)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(line + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
