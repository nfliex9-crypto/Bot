from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from config.settings import settings
from core.enums import Direction, Market, TradeStatus
from core.events import event_bus
from core.models import TradeRecord
from data.feed import DataFeed
from database.repository import TradeRepository
from execution.base import BaseExecutor
from risk.manager import RiskManager

logger = logging.getLogger(__name__)


class TradeManager:
    """
    Manages the lifecycle of open trades:
      - TP1/TP2/TP3 monitoring with partial closes
      - Break-even after TP1
      - Stop loss monitoring
      - PnL tracking
    """

    def __init__(
        self,
        executor: BaseExecutor,
        feed: DataFeed,
        risk_mgr: RiskManager,
        repo: TradeRepository,
    ) -> None:
        self._executor = executor
        self._feed = feed
        self._risk = risk_mgr
        self._repo = repo
        self._open_trades: Dict[str, TradeRecord] = {}

    @property
    def open_trades(self) -> Dict[str, TradeRecord]:
        return self._open_trades

    async def open_trade(self, trade: TradeRecord) -> bool:
        order_id = await self._executor.open_trade(trade)
        if order_id is None:
            trade.status = TradeStatus.CANCELLED
            trade.close_reason = "Execution failed"
            return False

        trade.broker_order_id = order_id
        trade.status = TradeStatus.OPEN
        self._open_trades[trade.id] = trade

        await self._repo.save_trade(trade)
        await event_bus.emit("trade_opened", trade)
        logger.info("Trade opened: %s %s %s @ %.5f", trade.id[:8], trade.direction.value, trade.symbol, trade.entry_price)
        return True

    async def monitor_trades(self) -> None:
        closed_ids = []

        for trade_id, trade in list(self._open_trades.items()):
            try:
                current_price = await self._feed.get_current_price(trade.symbol)
                if current_price <= 0:
                    continue

                if self._risk.check_stop_loss(trade, current_price):
                    await self._close_trade(trade, current_price, "stop_loss")
                    closed_ids.append(trade_id)
                    continue

                tp_hits = self._risk.check_tp_hits(trade, current_price)

                if "tp3" in tp_hits:
                    await self._close_trade(trade, current_price, "tp3_hit")
                    closed_ids.append(trade_id)
                    continue

                if "tp1" in tp_hits and not trade.tp1_hit:
                    trade.tp1_hit = True
                    await self._executor.partial_close(trade, 0.33)
                    logger.info("TP1 hit: %s — partial close 33%%", trade.symbol)

                    if settings.breakeven_after_tp1:
                        be_sl = self._risk.check_breakeven(trade, current_price)
                        if be_sl is not None:
                            await self._executor.modify_sl(trade, be_sl)
                            trade.stop_loss = be_sl
                            trade.breakeven_set = True
                            logger.info("Break-even set: %s sl=%.5f", trade.symbol, be_sl)

                if "tp2" in tp_hits and not trade.tp2_hit:
                    trade.tp2_hit = True
                    await self._executor.partial_close(trade, 0.50)
                    logger.info("TP2 hit: %s — partial close 50%%", trade.symbol)

                trade.pnl = await self._executor.get_open_pnl(trade, current_price)
                await self._repo.update_trade(trade)

            except Exception:
                logger.exception("Error monitoring trade %s", trade_id[:8])

        for tid in closed_ids:
            self._open_trades.pop(tid, None)

    async def _close_trade(
        self, trade: TradeRecord, current_price: float, reason: str
    ) -> None:
        pnl = await self._executor.get_open_pnl(trade, current_price)
        trade.pnl = pnl
        trade.pnl_pct = (pnl / trade.risk_amount * 100) if trade.risk_amount > 0 else 0.0
        trade.status = TradeStatus.CLOSED
        trade.close_reason = reason
        trade.closed_at = datetime.utcnow()

        await self._executor.close_trade(trade, reason)
        self._risk.update_account_pnl(trade)
        await self._repo.update_trade(trade)
        await event_bus.emit("trade_closed", trade)

        logger.info(
            "Trade closed: %s %s reason=%s pnl=%.2f (%.1f%%)",
            trade.symbol, trade.direction.value, reason, pnl, trade.pnl_pct,
        )

    async def close_all(self, reason: str = "manual") -> int:
        count = 0
        for trade_id, trade in list(self._open_trades.items()):
            current_price = await self._feed.get_current_price(trade.symbol)
            await self._close_trade(trade, current_price, reason)
            count += 1
        self._open_trades.clear()
        return count

    async def load_open_trades(self) -> None:
        rows = await self._repo.get_open_trades()
        for row in rows:
            trade = TradeRecord(
                id=row["id"],
                signal_id=row["signal_id"],
                symbol=row["symbol"],
                market=Market(row["market"]),
                direction=Direction(row["direction"]),
                status=TradeStatus(row["status"]),
                entry_price=row["entry_price"],
                stop_loss=row["stop_loss"],
                tp1=row["tp1"],
                tp2=row["tp2"],
                tp3=row["tp3"],
                tp1_hit=row["tp1_hit"],
                tp2_hit=row["tp2_hit"],
                tp3_hit=row["tp3_hit"],
                breakeven_set=row["breakeven_set"],
                position_size=row["position_size"],
                risk_amount=row["risk_amount"],
                confidence=row["confidence"],
                broker_order_id=row["broker_order_id"],
            )
            self._open_trades[trade.id] = trade
        logger.info("Loaded %d open trades from DB", len(self._open_trades))
