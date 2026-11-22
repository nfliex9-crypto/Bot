"""Sentinel Crypto read-only local dashboard service.

Independent of MT5, exchange credentials, accounts and any order executors.
Only GET '/' and '/api/status' are supported. No public bind or write API.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / "dashboard" / "index.html"
STATE = ROOT / "data" / "market_status.json"
SYMBOLS = ("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT")


def status_for_dashboard(source: Path, now_ms: int) -> dict:
    result = {
        "product": "SENTINEL_CRYPTO_FUTURES",
        "market_type": "USDT_LINEAR_PERPETUAL",
        "venue": "WEEX",
        "demo_account": "NOT_CONNECTED",
        "execution": "DISABLED",
        "markets": {},
    }
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return result
    if not isinstance(payload, dict) or payload.get("venue") != "WEEX":
        return result
    if payload.get("market_type") != "USDT_LINEAR_PERPETUAL":
        return result
    sources = payload.get("markets")
    if not isinstance(sources, dict):
        return result
    for symbol in SYMBOLS:
        entry = sources.get(symbol)
        if not isinstance(entry, dict):
            continue
        stamp = entry.get("received_ms")
        try:
            age = now_ms - int(stamp)
            bid, ask, last = (float(entry[k]) for k in ("bid", "ask", "last"))
            trades = int(entry["trades_seen"])
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if not (0 <= age <= 15000 and 0 < bid < ask and last > 0 and trades > 0
                and entry.get("verified_source") == "CCXT_PRO_WEEX_PUBLIC_FUTURES"):
            continue
        result["markets"][symbol] = {
            "status": "LIVE", "fresh": True, "bid": bid, "ask": ask,
            "last": last, "trades_seen": trades, "observed_at_ms": int(stamp)
        }
    return result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                data = VIEW.read_bytes()
            except OSError:
                self.send_error(503, "Dashboard missing")
                return
            content_type = "text/html; charset=utf-8"
        elif self.path == "/api/status":
            data = json.dumps(status_for_dashboard(STATE, int(time.time() * 1000)),
                              separators=(",", ":")).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif self.path == "/health":
            data = b'{"status":"UP","execution":"DISABLED"}'
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404, "Unknown read-only route")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        self.send_error(405, "Read-only server; orders disabled")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        p.error("Dashboard binds to localhost only; authenticated ingress must be designed separately")
    with ThreadingHTTPServer((args.host, args.port), Handler) as httpd:
        print(f"Sentinel Crypto read-only dashboard: http://{args.host}:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
