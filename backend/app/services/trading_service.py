"""
Trading Service

High-level service layer that coordinates between the execution engine,
database persistence, and API responses.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.db.models import Trade, Signal, EquitySnapshot, MarketType, OrderSide, TradeStatus, SignalStatus
from app.execution.execution_engine import ExecutionEngine
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: Optional[ExecutionEngine] = None


def get_execution_engine() -> ExecutionEngine:
    global _engine
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine


class TradingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = get_execution_engine()

    async def scan_and_signal(self, user_id: UUID) -> list[dict]:
        signals = await self.engine.scan_markets()

        for sig in signals:
            db_signal = Signal(
                user_id=user_id,
                symbol=sig["symbol"],
                market_type=MarketType(sig["market_type"]),
                side=OrderSide.BUY if sig["direction"] == "long" else OrderSide.SELL,
                entry_zone_low=sig["entry_price"] * 0.999,
                entry_zone_high=sig["entry_price"] * 1.001,
                stop_loss=sig["stop_loss"],
                take_profit_1=sig["take_profit_1"],
                take_profit_2=sig["take_profit_2"],
                take_profit_3=sig["take_profit_3"],
                ai_confidence=sig["confidence"],
                strategy_name=sig["strategy"],
                strategy_details=sig.get("details"),
                timeframe=sig["timeframe"],
            )
            self.db.add(db_signal)
            sig["signal_id"] = str(db_signal.id)

        await self.db.flush()
        return signals

    async def execute_trade(self, user_id: UUID, signal: dict) -> dict:
        result = await self.engine.execute_signal(signal)

        if result.get("executed"):
            trade = Trade(
                user_id=user_id,
                symbol=signal["symbol"],
                market_type=MarketType(signal["market_type"]),
                side=OrderSide.BUY if signal["direction"] == "long" else OrderSide.SELL,
                status=TradeStatus.OPEN,
                entry_price=result.get("entry_price", signal["entry_price"]),
                stop_loss=signal["stop_loss"],
                take_profit_1=signal["take_profit_1"],
                take_profit_2=signal["take_profit_2"],
                take_profit_3=signal["take_profit_3"],
                lot_size=result["lot_size"],
                risk_amount=result.get("risk_amount"),
                risk_percent=self.engine.settings.risk_per_trade,
                ai_confidence=signal["confidence"],
                strategy_name=signal["strategy"],
                external_order_id=result["order_id"],
            )
            self.db.add(trade)
            await self.db.flush()
            result["trade_id"] = str(trade.id)

            if signal.get("signal_id"):
                stmt = select(Signal).where(Signal.id == UUID(signal["signal_id"]))
                db_result = await self.db.execute(stmt)
                db_signal = db_result.scalar_one_or_none()
                if db_signal:
                    db_signal.status = SignalStatus.EXECUTED

        return result

    async def get_trade_history(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> list[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.user_id == user_id)
            .order_by(desc(Trade.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_signals(self, user_id: UUID) -> list[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.user_id == user_id, Signal.status == SignalStatus.ACTIVE)
            .order_by(desc(Signal.created_at))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def snapshot_equity(self, user_id: UUID) -> EquitySnapshot:
        dashboard = await self.engine.get_dashboard_data()
        equity_data = dashboard["equity"]
        risk_data = dashboard["risk_status"]

        snapshot = EquitySnapshot(
            user_id=user_id,
            balance=equity_data["total"],
            equity=equity_data["total"],
            drawdown=risk_data["current_drawdown"],
            drawdown_percent=risk_data["current_drawdown"],
            peak_equity=risk_data["peak_equity"],
            open_trades=risk_data["active_trades"],
        )
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_equity_history(
        self, user_id: UUID, limit: int = 100
    ) -> list[EquitySnapshot]:
        stmt = (
            select(EquitySnapshot)
            .where(EquitySnapshot.user_id == user_id)
            .order_by(desc(EquitySnapshot.timestamp))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
