from __future__ import annotations

from datetime import datetime

import pandas as pd


class BinanceMarketClient:
    def __init__(self, api_key: str | None, api_secret: str | None, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.client = None

        try:
            from binance.client import Client

            self.client = Client(api_key=api_key, api_secret=api_secret, testnet=testnet)
        except Exception:
            self.client = None

    def get_klines(self, symbol: str, interval: str = "5m", limit: int = 200) -> pd.DataFrame:
        if self.client is None:
            return pd.DataFrame()

        klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        if not klines:
            return pd.DataFrame()

        frame = pd.DataFrame(
            klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )
        frame["time"] = pd.to_datetime(frame["open_time"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            frame[col] = frame[col].astype(float)
        return frame[["time", "open", "high", "low", "close", "volume"]]

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        if self.client is None:
            return {"ok": False, "simulated": True, "reason": "binance_unavailable"}

        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=max(quantity, 0.0),
                newClientOrderId=f"ai-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            )
            return {"ok": True, "simulated": False, "order_id": str(order.get("orderId")), "raw": order}
        except Exception as exc:
            return {"ok": False, "simulated": True, "reason": str(exc)}
