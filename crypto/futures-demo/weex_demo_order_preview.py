"""WEEX Demo-Futures order creation PREVIEW using official CCXT contract builder.

Never calls create_order, never authenticates a live account, and never transmits
any private order request. Shows ONLY a sanitized order template & target host.
"""
from __future__ import annotations

import argparse
import json
import math
from urllib.parse import urlsplit

from weex_futures_feed import PAIRS, verify_swap, positive
from weex_demo_guard import WEEXDemoOnly, SIM_BASE, SandboxBoundaryError


class PreviewRejected(ValueError):
    pass


def preview_order(exchange, symbol: str, side: str, market: dict,
                  book: dict) -> dict:
    if side not in ("buy", "sell") or symbol not in PAIRS:
        raise PreviewRejected("INVALID_PERPETUAL_OR_SIDE")
    verify_swap(market, symbol)
    if not isinstance(book, dict):
        raise PreviewRejected("MISSING_REAL_CONTRACT_BOOK")
    try:
        bid, bid_amount = book["bids"][0][:2]
        ask, ask_amount = book["asks"][0][:2]
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise PreviewRejected("BOOK_TOP_LEVEL_MISSING") from exc
    if not all(positive(x) for x in (bid, ask, bid_amount, ask_amount)) or bid >= ask:
        raise PreviewRejected("INVALID_FUTURES_BOOK_BBO")
    limits = market.get("limits") or {}
    min_amount = (limits.get("amount") or {}).get("min")
    if not positive(min_amount):
        raise PreviewRejected("EXCHANGE_MINIMUM_CONTRACT_QUANTITY_UNAVAILABLE")
    raw_price = float(bid) if side == "buy" else float(ask)
    # Produce a template using CCXT's native contract precision and order builder.
    # This method constructs but does not transmit any HTTP request.
    request = exchange.create_contract_order_request(
        symbol, "limit", side, float(min_amount), raw_price,
        {"timeInForce": "GTC", "clientOrderId": "SENTINEL-PREVIEW-ONLY"},
    )
    signed = exchange.sign("capi/v3/order", ["contractPrivate"], "POST", request)
    host = urlsplit(signed["url"])
    if (host.scheme, host.netloc) != ("https", "api-sim.weex.com"):
        raise SandboxBoundaryError("PUBLIC_OR_PRODUCTION_ORDER_TARGET_REJECTED")
    if request.get("symbol") != market.get("id") or request.get("side") != side.upper():
        raise PreviewRejected("UPSTREAM_CONTRACT_ORDER_REQUEST_NOT_MATCHED")
    if request.get("type") != "LIMIT" or not positive(request.get("quantity")):
        raise PreviewRejected("INVALID_UPSTREAM_CONTRACT_ORDER_QUANTITY")
    return {
        "status": "WEEX_FUTURES_DEMO_ORDER_PREVIEW_ONLY",
        "venue": "WEEX", "market": "USDT_LINEAR_PERPETUAL", "symbol": symbol,
        "order_side": side, "order_type": "limit", "time_in_force": "GTC",
        "quantity_in_exchange_units": request["quantity"],
        "candidate_price_not_submitted": request.get("price"),
        "source": "official_ccxt_4.5.93_futures_market_and_order_builder",
        "destination_host": host.netloc, "actual_http_requests_sent_for_order": 0,
        "simulated_exchange_orders_placed": 0, "live_orders_placed": 0,
        "read_only": True,
        "note": "Preview is an upstream-formatted order request, NOT an accepted demo order",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WEEX Futures Demo-only safe ORDER PREVIEW (never sends)")
    parser.add_argument("--symbol", choices=PAIRS, default=PAIRS[0])
    parser.add_argument("--side", choices=("buy", "sell"), default="buy")
    args = parser.parse_args()
    exchange = WEEXDemoOnly({
        "apiKey": "PREVIEW_ONLY_NOT_AUTHENTIC",
        "secret": "PREVIEW_ONLY_NOT_AUTHENTIC",
        "password": "PREVIEW_ONLY_NOT_AUTHENTIC",
    })
    try:
        exchange.load_markets()
        market = exchange.market(args.symbol)
        book = exchange.fetch_order_book(args.symbol, 15)
        result = preview_order(exchange, args.symbol, args.side, market, book)
        code = 0
    except Exception as exc:
        result = {
            "status": "DEMO_ORDER_PREVIEW_NOT_VERIFIED", "error_type": type(exc).__name__,
            "symbol": args.symbol, "actual_http_requests_sent_for_order": 0,
            "simulated_exchange_orders_placed": 0, "live_orders_placed": 0,
        }
        code = 1
    finally:
        exchange.close()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
