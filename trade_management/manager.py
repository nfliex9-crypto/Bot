"""
Trade management: partial take-profits, break-even adjustment,
trailing stop, and position monitoring.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from config.settings import StrategyConfig
from core.logger import get_logger
from core.models import Direction, Trade, TradeStatus

logger = get_logger("trade.manager")


class TradeManager:
    """
    Manages open trades:
    - TP1 hit → close 40%, move SL to break-even
    - TP2 hit → close 30%
    - TP3 hit → close remaining 30%
    """

    TP1_CLOSE_PCT = 0.40
    TP2_CLOSE_PCT = 0.30
    TP3_CLOSE_PCT = 0.30

    def __init__(self, config: StrategyConfig):
        self.config = config

    def check_trade(self, trade: Trade, current_price: float) -> List[dict]:
        """
        Check if any TP or SL has been hit.
        Returns a list of action dicts: {"action": ..., "details": ...}
        """
        actions = []

        if trade.status not in (TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE):
            return actions

        trade.current_price = current_price

        if self._sl_hit(trade, current_price):
            actions.append({
                "action": "close_full",
                "reason": "stop_loss",
                "price": current_price,
                "pnl": self._calc_pnl(trade, current_price),
            })
            return actions

        if not trade.tp1_hit and self._tp_hit(trade, current_price, trade.tp1):
            trade.tp1_hit = True
            trade.status = TradeStatus.PARTIAL_CLOSE
            close_size = trade.position_size * self.TP1_CLOSE_PCT
            actions.append({
                "action": "partial_close",
                "reason": "tp1",
                "size": close_size,
                "price": current_price,
                "pnl": self._calc_partial_pnl(trade, current_price, close_size),
            })

            if self.config.breakeven_after_tp1:
                old_sl = trade.stop_loss
                trade.stop_loss = trade.entry_price
                trade.breakeven_set = True
                actions.append({
                    "action": "move_sl",
                    "reason": "breakeven",
                    "old_sl": old_sl,
                    "new_sl": trade.entry_price,
                })
                logger.info(f"{trade.trade_id}: SL moved to BE @ {trade.entry_price:.5f}")

        if not trade.tp2_hit and trade.tp1_hit and self._tp_hit(trade, current_price, trade.tp2):
            trade.tp2_hit = True
            remaining = trade.position_size * (1 - self.TP1_CLOSE_PCT)
            close_size = trade.position_size * self.TP2_CLOSE_PCT
            actions.append({
                "action": "partial_close",
                "reason": "tp2",
                "size": close_size,
                "price": current_price,
                "pnl": self._calc_partial_pnl(trade, current_price, close_size),
            })

        if not trade.tp3_hit and trade.tp2_hit and self._tp_hit(trade, current_price, trade.tp3):
            trade.tp3_hit = True
            remaining = trade.position_size * self.TP3_CLOSE_PCT
            actions.append({
                "action": "close_full",
                "reason": "tp3",
                "price": current_price,
                "pnl": self._calc_partial_pnl(trade, current_price, remaining),
            })

        return actions

    def _sl_hit(self, trade: Trade, price: float) -> bool:
        if trade.direction == Direction.LONG:
            return price <= trade.stop_loss
        return price >= trade.stop_loss

    def _tp_hit(self, trade: Trade, price: float, tp: float) -> bool:
        if trade.direction == Direction.LONG:
            return price >= tp
        return price <= tp

    def _calc_pnl(self, trade: Trade, price: float) -> float:
        if trade.direction == Direction.LONG:
            return (price - trade.entry_price) * trade.position_size
        return (trade.entry_price - price) * trade.position_size

    def _calc_partial_pnl(self, trade: Trade, price: float, size: float) -> float:
        if trade.direction == Direction.LONG:
            return (price - trade.entry_price) * size
        return (trade.entry_price - price) * size

    def get_unrealized_pnl(self, trades: List[Trade]) -> float:
        total = 0.0
        for t in trades:
            if t.status in (TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE):
                total += self._calc_pnl(t, t.current_price)
        return total
