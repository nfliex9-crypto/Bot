from __future__ import annotations

from typing import Any

from app.core.config import get_settings

settings = get_settings()

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional runtime dependency
    mt5 = None


class MT5ExecutionEngine:
    def place_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        stop_loss: float,
        take_profit: float,
    ) -> dict[str, Any]:
        if mt5 is None:
            return {"status": "paper", "broker": "mt5", "symbol": symbol, "side": side}

        if not mt5.initialize(
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        ):
            return {"status": "error", "broker": "mt5", "message": "initialize failed"}

        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "deviation": 20,
            "magic": 920001,
            "comment": "ai-trading-system",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        mt5.shutdown()

        if result is None:
            return {"status": "error", "broker": "mt5", "message": "order_send failed"}

        return {"status": "ok", "broker": "mt5", "result_code": getattr(result, "retcode", None)}
