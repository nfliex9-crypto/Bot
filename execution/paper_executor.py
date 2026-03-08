from __future__ import annotations

import logging
import uuid
from typing import Optional

from core.enums import Direction
from core.models import TradeRecord
from execution.base import BaseExecutor

logger = logging.getLogger(__name__)


class PaperExecutor(BaseExecutor):
    """Simulated execution for paper trading mode — no real orders."""

    async def open_trade(self, trade: TradeRecord) -> Optional[str]:
        order_id = f"PAPER-{uuid.uuid4().hex[:12]}"
        logger.info(
            "[PAPER] Opened %s %s @ %.5f size=%.4f sl=%.5f tp1=%.5f tp2=%.5f tp3=%.5f",
            trade.direction.value, trade.symbol, trade.entry_price,
            trade.position_size, trade.stop_loss, trade.tp1, trade.tp2, trade.tp3,
        )
        return order_id

    async def close_trade(self, trade: TradeRecord, reason: str = "") -> bool:
        logger.info("[PAPER] Closed %s %s reason=%s pnl=%.2f", trade.direction.value, trade.symbol, reason, trade.pnl)
        return True

    async def partial_close(self, trade: TradeRecord, fraction: float) -> bool:
        close_qty = trade.position_size * fraction
        trade.position_size -= close_qty
        logger.info("[PAPER] Partial close %s %.4f (remaining: %.4f)", trade.symbol, close_qty, trade.position_size)
        return True

    async def modify_sl(self, trade: TradeRecord, new_sl: float) -> bool:
        old_sl = trade.stop_loss
        trade.stop_loss = new_sl
        logger.info("[PAPER] SL modified %s %.5f -> %.5f", trade.symbol, old_sl, new_sl)
        return True

    async def get_open_pnl(self, trade: TradeRecord, current_price: float) -> float:
        if trade.direction == Direction.LONG:
            return (current_price - trade.entry_price) * trade.position_size * 100000
        else:
            return (trade.entry_price - current_price) * trade.position_size * 100000
