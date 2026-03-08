from __future__ import annotations

from app.core.config import Settings
from app.services.execution.types import OrderRequest, OrderResult

try:
    from binance.client import Client
except Exception:  # pragma: no cover - optional dependency
    Client = None


class BinanceExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = None
        if Client and settings.binance_api_key and settings.binance_api_secret:
            self.client = Client(settings.binance_api_key, settings.binance_api_secret)

    def execute(self, request: OrderRequest) -> OrderResult:
        if self.settings.paper_mode or self.client is None:
            return OrderResult(
                success=True,
                order_id=f"paper-binance-{request.symbol}",
                mode="paper",
                message="Binance paper execution",
            )

        side = "BUY" if request.side.lower() == "buy" else "SELL"
        try:
            result = self.client.create_order(
                symbol=request.symbol,
                side=side,
                type="MARKET",
                quantity=round(request.quantity, 6),
            )
            return OrderResult(True, str(result.get("orderId", "")), "live", "Binance order placed")
        except Exception as exc:  # pragma: no cover - network/runtime path
            return OrderResult(False, "", "live", f"Binance error: {exc}")
