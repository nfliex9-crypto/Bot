from __future__ import annotations

from uuid import uuid4

from app.config import Settings
from app.execution.base import ExecutionResult, OrderRequest


class BinanceExecutor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        try:
            from binance.client import Client  # type: ignore

            self._client = Client(settings.binance_api_key, settings.binance_api_secret, testnet=settings.binance_testnet)
        except Exception:
            self._client = None

    def place_order(self, req: OrderRequest) -> ExecutionResult:
        if self._client is None:
            return ExecutionResult(
                accepted=False,
                order_id=f"binance-sim-{uuid4().hex[:8]}",
                message="Binance client unavailable, cannot place live order",
                raw={"reason": "binance_not_connected"},
            )

        side = "BUY" if req.side == "buy" else "SELL"
        try:
            order = self._client.create_order(
                symbol=req.symbol,
                side=side,
                type="MARKET",
                quantity=round(req.quantity, 6),
            )
            return ExecutionResult(
                accepted=True,
                order_id=str(order.get("orderId", "")),
                message="Binance market order placed",
                raw=order,
            )
        except Exception as exc:  # pragma: no cover - exchange runtime
            return ExecutionResult(
                accepted=False,
                order_id="",
                message=f"Binance order failed: {exc}",
                raw={"error": str(exc)},
            )

