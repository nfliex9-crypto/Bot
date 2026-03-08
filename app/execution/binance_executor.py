from __future__ import annotations

from app.execution.base import BaseExecutor, OrderRequest, OrderResult

try:
    from binance.client import Client
except Exception:  # pragma: no cover
    Client = None  # type: ignore[assignment]


class BinanceExecutor(BaseExecutor):
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        if Client is None:
            raise RuntimeError("python-binance is not available.")
        self.client = Client(api_key=api_key, api_secret=api_secret, testnet=testnet)

    def place_order(self, request: OrderRequest) -> OrderResult:
        side = "BUY" if request.side == "buy" else "SELL"
        order = self.client.create_order(
            symbol=request.symbol,
            side=side,
            type="MARKET",
            quantity=round(request.quantity, 6),
        )
        fills = order.get("fills") or []
        fill_price = request.price
        if fills:
            fill_price = float(fills[0].get("price", request.price))
        return OrderResult(
            success=True,
            execution_ref=str(order.get("orderId")),
            filled_price=fill_price,
            message="Binance market order filled.",
        )

    def close_partial(self, symbol: str, side: str, quantity: float) -> OrderResult:
        close_side = "SELL" if side == "buy" else "BUY"
        order = self.client.create_order(
            symbol=symbol,
            side=close_side,
            type="MARKET",
            quantity=round(quantity, 6),
        )
        return OrderResult(
            success=True,
            execution_ref=str(order.get("orderId")),
            filled_price=0.0,
            message="Binance partial close executed.",
        )

