from __future__ import annotations

from typing import Any

from app.core.config import get_settings

settings = get_settings()

try:
    from binance.client import Client as BinanceClient
except Exception:  # pragma: no cover - optional runtime dependency
    BinanceClient = None


class BinanceExecutionEngine:
    def __init__(self) -> None:
        self.client = None
        if BinanceClient and settings.binance_api_key and settings.binance_api_secret:
            self.client = BinanceClient(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret,
                testnet=settings.binance_testnet,
            )

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict[str, Any]:
        if not self.client:
            return {"status": "paper", "broker": "binance", "symbol": symbol, "side": side}

        order_side = "BUY" if side == "buy" else "SELL"
        result = self.client.order_market(symbol=symbol, side=order_side, quantity=quantity)
        return {"status": "ok", "broker": "binance", "order_id": result.get("orderId")}
