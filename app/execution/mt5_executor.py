from __future__ import annotations

import logging
from uuid import uuid4

from app.config import Settings
from app.execution.base import ExecutionResult, OrderRequest
from app.market.mt5_client import MT5MarketDataClient

logger = logging.getLogger(__name__)


class MT5Executor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = MT5MarketDataClient(settings)
        self._mt5 = self.client._mt5
        self.client.connect()

    def place_order(self, req: OrderRequest) -> ExecutionResult:
        if self._mt5 is None or not self.client.connected:
            return ExecutionResult(
                accepted=False,
                order_id=f"mt5-sim-{uuid4().hex[:8]}",
                message="MT5 unavailable, cannot place live order",
                raw={"reason": "mt5_not_connected"},
            )

        order_type = self._mt5.ORDER_TYPE_BUY if req.side == "buy" else self._mt5.ORDER_TYPE_SELL
        tick = self._mt5.symbol_info_tick(req.symbol)
        if tick is None:
            return ExecutionResult(False, "", f"Symbol tick unavailable for {req.symbol}", raw={})
        price = tick.ask if req.side == "buy" else tick.bid
        request = {
            "action": self._mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.quantity),
            "type": order_type,
            "price": price,
            "sl": float(req.stop_loss),
            "tp": float(req.tp1),
            "deviation": 20,
            "magic": 20260308,
            "comment": "AI Trading Bot",
            "type_time": self._mt5.ORDER_TIME_GTC,
            "type_filling": self._mt5.ORDER_FILLING_IOC,
        }
        result = self._mt5.order_send(request)
        if result is None:
            return ExecutionResult(False, "", "MT5 returned no result", raw={"request": request})
        accepted = getattr(result, "retcode", None) == self._mt5.TRADE_RETCODE_DONE
        order_id = str(getattr(result, "order", ""))
        return ExecutionResult(
            accepted=accepted,
            order_id=order_id,
            message=f"MT5 retcode={getattr(result, 'retcode', None)}",
            raw={"request": request, "result": str(result)},
        )

