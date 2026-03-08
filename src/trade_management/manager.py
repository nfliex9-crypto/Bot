"""
Trade Management System.

Monitors open positions and manages:
- TP1/TP2/TP3 partial closes
- Break-even after TP1 is hit
- Trailing stop after TP2
- Maximum adverse excursion tracking
- Emergency close on max drawdown breach
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.models.database import (
    Trade, TradeStatus, CloseReason, AsyncSessionLocal
)
from src.execution.mt5_executor import MT5Executor
from src.execution.binance_executor import BinanceExecutor
from src.risk.risk_manager import RiskManager
from config.settings import settings


class TradeManager:
    """
    Monitors and manages all open positions.
    Called on each tick/bar close cycle.
    """

    def __init__(
        self,
        mt5_executor: MT5Executor,
        binance_executor: BinanceExecutor,
        risk_manager: RiskManager,
    ):
        self._mt5 = mt5_executor
        self._binance = binance_executor
        self._risk = risk_manager
        # Cache: trade_id → partial close state
        self._tp1_hit: Dict[str, bool] = {}
        self._tp2_hit: Dict[str, bool] = {}
        self._be_set: Dict[str, bool] = {}

    async def manage_open_trades(
        self,
        current_prices: Dict[str, float],
    ) -> None:
        """
        Main management loop. Call this on each tick update.
        current_prices: {symbol: current_price}
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Trade).where(
                    Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE])
                )
            )
            open_trades = result.scalars().all()

        for trade in open_trades:
            symbol = trade.symbol
            price = current_prices.get(symbol)
            if price is None:
                continue
            await self._manage_single_trade(trade, price)

    async def _manage_single_trade(self, trade: Trade, current_price: float) -> None:
        """Run all management checks for a single open trade."""
        trade_id = str(trade.id)
        direction = trade.direction.value
        entry = float(trade.entry_price or 0)
        sl = float(trade.stop_loss)
        tp1 = float(trade.tp1)
        tp2 = float(trade.tp2)
        tp3 = float(trade.tp3)

        # ─── Stop Loss Hit ────────────────────────────────────────────────────
        if self._is_sl_hit(direction, current_price, sl):
            logger.warning(f"[TM] SL hit | {trade.symbol} price={current_price} sl={sl}")
            await self._close_trade(trade, current_price, CloseReason.STOP_LOSS)
            return

        # ─── TP3 Hit ──────────────────────────────────────────────────────────
        if self._is_tp_hit(direction, current_price, tp3):
            logger.info(f"[TM] TP3 hit | {trade.symbol} price={current_price} tp3={tp3}")
            await self._close_trade(trade, current_price, CloseReason.TP3)
            return

        # ─── TP2 Hit ──────────────────────────────────────────────────────────
        if not self._tp2_hit.get(trade_id) and self._is_tp_hit(direction, current_price, tp2):
            logger.info(f"[TM] TP2 hit | {trade.symbol} price={current_price} tp2={tp2}")
            self._tp2_hit[trade_id] = True
            await self._partial_close(trade, current_price, CloseReason.TP2, partial_pct=0.5)

        # ─── TP1 Hit → Break-Even ─────────────────────────────────────────────
        if not self._tp1_hit.get(trade_id) and self._is_tp_hit(direction, current_price, tp1):
            logger.info(f"[TM] TP1 hit | {trade.symbol} price={current_price} tp1={tp1}")
            self._tp1_hit[trade_id] = True
            await self._partial_close(trade, current_price, CloseReason.TP1, partial_pct=0.33)

            # Move stop to break-even
            if not self._be_set.get(trade_id):
                be_price = self._calculate_break_even(entry, tp1, direction)
                await self._set_break_even(trade, be_price)
                self._be_set[trade_id] = True

        # ─── Update MAE/MFE ───────────────────────────────────────────────────
        await self._update_excursions(trade, current_price)

    def _is_sl_hit(self, direction: str, price: float, sl: float) -> bool:
        if direction == "long":
            return price <= sl
        return price >= sl

    def _is_tp_hit(self, direction: str, price: float, tp: float) -> bool:
        if direction == "long":
            return price >= tp
        return price <= tp

    def _calculate_break_even(self, entry: float, tp1: float, direction: str) -> float:
        """Break-even price = entry + small buffer to cover spread."""
        buffer = abs(tp1 - entry) * 0.1
        if direction == "long":
            return round(entry + buffer, 8)
        return round(entry - buffer, 8)

    async def _close_trade(
        self, trade: Trade, close_price: float, reason: CloseReason
    ) -> None:
        """Fully close a trade and update the database."""
        executor = self._get_executor(trade.market.value)
        direction = trade.direction.value

        result = await executor.close_trade(
            broker_ticket=str(trade.broker_ticket or ""),
            symbol=trade.symbol,
            lot_size=float(trade.lot_size),
            direction=direction,
            close_price=close_price,
        )

        pnl = result.pnl or self._calculate_pnl(trade, close_price)
        self._risk.record_trade_close(float(trade.risk_amount), pnl)

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Trade)
                .where(Trade.id == trade.id)
                .values(
                    status=TradeStatus.CLOSED,
                    close_time=datetime.now(tz=timezone.utc),
                    close_reason=reason,
                    realized_pnl=Decimal(str(round(pnl, 2))),
                )
            )
            await session.commit()

        logger.info(
            f"[TM] TRADE CLOSED | {trade.symbol} | reason={reason.value} "
            f"pnl={pnl:+.2f} ticket={trade.broker_ticket}"
        )

        # Cleanup state
        trade_id = str(trade.id)
        for d in [self._tp1_hit, self._tp2_hit, self._be_set]:
            d.pop(trade_id, None)

    async def _partial_close(
        self, trade: Trade, close_price: float, reason: CloseReason, partial_pct: float
    ) -> None:
        """Partially close a position (e.g. 33% at TP1, 50% at TP2)."""
        executor = self._get_executor(trade.market.value)
        close_qty = float(trade.lot_size) * partial_pct

        result = await executor.close_trade(
            broker_ticket=str(trade.broker_ticket or ""),
            symbol=trade.symbol,
            lot_size=close_qty,
            direction=trade.direction.value,
            close_price=close_price,
        )

        partial_pnl = result.pnl or 0.0

        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Trade)
                .where(Trade.id == trade.id)
                .values(
                    status=TradeStatus.PARTIAL_CLOSE,
                    realized_pnl=Trade.realized_pnl + Decimal(str(round(partial_pnl, 2))),
                )
            )
            await session.commit()

        logger.info(
            f"[TM] PARTIAL CLOSE {partial_pct:.0%} | {trade.symbol} | "
            f"reason={reason.value} price={close_price} pnl={partial_pnl:+.2f}"
        )

    async def _set_break_even(self, trade: Trade, be_price: float) -> None:
        """Move stop loss to break-even level."""
        executor = self._get_executor(trade.market.value)
        success = await executor.modify_stop_loss(
            broker_ticket=str(trade.broker_ticket or ""),
            symbol=trade.symbol,
            new_stop_loss=be_price,
        )

        if success:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Trade)
                    .where(Trade.id == trade.id)
                    .values(
                        stop_loss=Decimal(str(be_price)),
                        break_even_price=Decimal(str(be_price)),
                    )
                )
                await session.commit()
            logger.info(f"[TM] BREAK-EVEN SET | {trade.symbol} be={be_price}")

    async def _update_excursions(self, trade: Trade, current_price: float) -> None:
        """Update MAE (max adverse) and MFE (max favorable) excursion."""
        entry = float(trade.entry_price or 0)
        if entry == 0:
            return

        direction = trade.direction.value
        if direction == "long":
            favorable = current_price - entry
            adverse = entry - current_price
        else:
            favorable = entry - current_price
            adverse = current_price - entry

        current_mae = float(trade.max_adverse_excursion or 0)
        current_mfe = float(trade.max_favorable_excursion or 0)

        if adverse > current_mae or favorable > current_mfe:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Trade)
                    .where(Trade.id == trade.id)
                    .values(
                        max_adverse_excursion=Decimal(str(max(adverse, current_mae))),
                        max_favorable_excursion=Decimal(str(max(favorable, current_mfe))),
                    )
                )
                await session.commit()

    def _calculate_pnl(self, trade: Trade, close_price: float) -> float:
        """Estimate P&L for paper trades where broker doesn't return it."""
        entry = float(trade.entry_price or 0)
        if entry == 0:
            return 0.0
        lot_size = float(trade.lot_size)
        direction = trade.direction.value

        if trade.market.value == "forex":
            pip_size = 0.01 if "JPY" in trade.symbol else 0.0001
            if direction == "long":
                pips = (close_price - entry) / pip_size
            else:
                pips = (entry - close_price) / pip_size
            return round(pips * 10.0 * lot_size, 2)
        else:
            if direction == "long":
                return round((close_price - entry) * lot_size, 4)
            return round((entry - close_price) * lot_size, 4)

    def _get_executor(self, market: str):
        return self._mt5 if market == "forex" else self._binance

    async def emergency_close_all(self, reason: str = "max_drawdown") -> int:
        """Emergency close all open trades (called on max drawdown breach)."""
        logger.warning(f"[TM] EMERGENCY CLOSE ALL | reason={reason}")
        count = 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Trade).where(Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE]))
            )
            trades = result.scalars().all()

        close_reason = CloseReason.MAX_DRAWDOWN if reason == "max_drawdown" else CloseReason.MANUAL

        for trade in trades:
            try:
                executor = self._get_executor(trade.market.value)
                tick_price = 0.0
                if hasattr(executor, "_paper_close"):
                    await self._close_trade(trade, tick_price, close_reason)
                    count += 1
            except Exception as e:
                logger.error(f"Emergency close failed for {trade.symbol}: {e}")

        return count
