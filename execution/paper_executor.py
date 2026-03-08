"""
Paper trading executor — simulates order fills without real money.
Maintains a virtual order book for backtesting and paper mode.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.models import Direction, Trade, TradeSignal, TradeStatus

logger = get_logger("execution.paper")


class PaperExecutor:
    """Simulates order execution for paper trading mode."""

    def __init__(self):
        self.filled_orders: list[dict] = []
        self.order_counter = 0

    async def place_order(self, signal: TradeSignal, size: float) -> Optional[Trade]:
        self.order_counter += 1
        fill_price = signal.entry_price

        trade = Trade(
            signal=signal,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            position_size=size,
            status=TradeStatus.OPEN,
            broker_order_id=f"PAPER-{self.order_counter}",
            market="paper",
        )

        self.filled_orders.append({
            "order_id": trade.broker_order_id,
            "symbol": signal.symbol,
            "direction": signal.direction.value,
            "size": size,
            "price": fill_price,
            "time": datetime.utcnow().isoformat(),
        })

        logger.info(
            f"[PAPER] Order filled: {trade.trade_id} {signal.symbol} "
            f"{signal.direction.value} {size} @ {fill_price:.5f}"
        )
        return trade

    async def close_position(self, trade: Trade, quantity: Optional[float] = None) -> bool:
        close_size = quantity or trade.position_size
        logger.info(
            f"[PAPER] Position closed: {trade.trade_id} {trade.symbol} "
            f"qty={close_size} @ {trade.current_price:.5f}"
        )
        self.filled_orders.append({
            "order_id": f"CLOSE-{trade.broker_order_id}",
            "symbol": trade.symbol,
            "direction": "close",
            "size": close_size,
            "price": trade.current_price,
            "time": datetime.utcnow().isoformat(),
        })
        return True

    async def modify_sl(self, trade: Trade, new_sl: float) -> bool:
        logger.info(f"[PAPER] SL modified: {trade.trade_id} → {new_sl:.5f}")
        return True
