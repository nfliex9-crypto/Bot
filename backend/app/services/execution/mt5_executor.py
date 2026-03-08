from __future__ import annotations

from app.core.config import Settings
from app.services.execution.types import OrderRequest, OrderResult

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mt5 = None


class MT5Executor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute(self, request: OrderRequest) -> OrderResult:
        if self.settings.paper_mode or mt5 is None:
            return OrderResult(
                success=True,
                order_id=f"paper-mt5-{request.symbol}",
                mode="paper",
                message="MT5 paper execution",
            )

        if not mt5.initialize(login=int(self.settings.mt5_login), password=self.settings.mt5_password, server=self.settings.mt5_server):
            return OrderResult(False, "", "live", "MT5 initialize failed")

        order_type = mt5.ORDER_TYPE_BUY if request.side.lower() == "buy" else mt5.ORDER_TYPE_SELL
        mt5_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": request.quantity,
            "type": order_type,
            "price": request.entry_price,
            "sl": request.stop_loss,
            "tp": request.tp1,
            "deviation": 20,
            "magic": 880011,
            "comment": "ai-trading-engine",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(mt5_request)
        mt5.shutdown()
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(False, "", "live", "MT5 order rejected")
        return OrderResult(True, str(result.order), "live", "MT5 order filled")
