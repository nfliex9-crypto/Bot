from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from core.enums import TradeStatus
from core.models import AccountState, TradeRecord, TradeSignal
from database.connection import get_session
from database.models import (
    AccountSnapshotDB,
    AIModelMetricDB,
    CandleDB,
    SignalLogDB,
    TradeRecordDB,
)

logger = logging.getLogger(__name__)


class TradeRepository:

    async def save_trade(self, trade: TradeRecord) -> None:
        async with get_session() as session:
            db_trade = TradeRecordDB(
                id=trade.id,
                signal_id=trade.signal_id,
                symbol=trade.symbol,
                market=trade.market.value,
                direction=trade.direction.value,
                status=trade.status.value,
                entry_price=trade.entry_price,
                stop_loss=trade.stop_loss,
                tp1=trade.tp1,
                tp2=trade.tp2,
                tp3=trade.tp3,
                position_size=trade.position_size,
                risk_amount=trade.risk_amount,
                confidence=trade.confidence,
                opened_at=trade.opened_at,
                broker_order_id=trade.broker_order_id,
                metadata_json=trade.metadata,
            )
            session.add(db_trade)

    async def update_trade(self, trade: TradeRecord) -> None:
        async with get_session() as session:
            await session.execute(
                update(TradeRecordDB)
                .where(TradeRecordDB.id == trade.id)
                .values(
                    status=trade.status.value,
                    tp1_hit=trade.tp1_hit,
                    tp2_hit=trade.tp2_hit,
                    tp3_hit=trade.tp3_hit,
                    breakeven_set=trade.breakeven_set,
                    pnl=trade.pnl,
                    pnl_pct=trade.pnl_pct,
                    closed_at=trade.closed_at,
                    close_reason=trade.close_reason,
                    stop_loss=trade.stop_loss,
                )
            )

    async def get_open_trades(self) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(
                select(TradeRecordDB).where(
                    TradeRecordDB.status.in_([TradeStatus.OPEN.value, TradeStatus.PARTIAL_CLOSE.value])
                )
            )
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def get_trades_since(self, since: datetime) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(
                select(TradeRecordDB).where(TradeRecordDB.opened_at >= since).order_by(TradeRecordDB.opened_at.desc())
            )
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def get_session_trade_count(self) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        async with get_session() as session:
            result = await session.execute(
                select(func.count(TradeRecordDB.id)).where(
                    TradeRecordDB.opened_at >= today_start,
                    TradeRecordDB.status != TradeStatus.CANCELLED.value,
                )
            )
            return result.scalar() or 0

    async def get_closed_trades(self, limit: int = 200) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(
                select(TradeRecordDB)
                .where(TradeRecordDB.status == TradeStatus.CLOSED.value)
                .order_by(TradeRecordDB.closed_at.desc())
                .limit(limit)
            )
            return [self._row_to_dict(row) for row in result.scalars().all()]

    async def log_signal(self, signal: TradeSignal, accepted: bool, reject_reason: str = "") -> None:
        async with get_session() as session:
            db_signal = SignalLogDB(
                id=signal.id,
                symbol=signal.symbol,
                market=signal.market.value,
                direction=signal.direction.value,
                signal_type=signal.signal_type.value,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                tp1=signal.tp1,
                tp2=signal.tp2,
                tp3=signal.tp3,
                confidence=signal.confidence,
                accepted=accepted,
                reject_reason=reject_reason,
                features_json=signal.features,
            )
            session.add(db_signal)

    async def save_account_snapshot(self, state: AccountState) -> None:
        async with get_session() as session:
            snapshot = AccountSnapshotDB(
                balance=state.balance,
                equity=state.equity,
                open_trades=state.open_trades,
                total_pnl=state.total_pnl,
                max_drawdown=state.max_drawdown,
                current_drawdown_pct=state.current_drawdown_pct,
                win_rate=state.win_rate,
                session_trades=state.session_trades,
            )
            session.add(snapshot)

    async def save_candles(self, candles: List[Dict]) -> None:
        if not candles:
            return
        async with get_session() as session:
            stmt = pg_insert(CandleDB).values(candles)
            stmt = stmt.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "timestamp"],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            await session.execute(stmt)

    async def save_ai_metrics(self, metrics: Dict) -> None:
        async with get_session() as session:
            entry = AIModelMetricDB(**metrics)
            session.add(entry)

    async def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        async with get_session() as session:
            result = await session.execute(
                select(SignalLogDB).order_by(SignalLogDB.created_at.desc()).limit(limit)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id, "symbol": r.symbol, "direction": r.direction,
                    "signal_type": r.signal_type, "confidence": r.confidence,
                    "accepted": r.accepted, "reject_reason": r.reject_reason,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    async def get_account_history(self, days: int = 30) -> List[Dict]:
        since = datetime.utcnow() - timedelta(days=days)
        async with get_session() as session:
            result = await session.execute(
                select(AccountSnapshotDB)
                .where(AccountSnapshotDB.snapshot_at >= since)
                .order_by(AccountSnapshotDB.snapshot_at.asc())
            )
            return [
                {
                    "balance": r.balance, "equity": r.equity,
                    "drawdown_pct": r.current_drawdown_pct,
                    "win_rate": r.win_rate,
                    "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
                }
                for r in result.scalars().all()
            ]

    @staticmethod
    def _row_to_dict(row: TradeRecordDB) -> Dict:
        return {
            "id": row.id,
            "signal_id": row.signal_id,
            "symbol": row.symbol,
            "market": row.market,
            "direction": row.direction,
            "status": row.status,
            "entry_price": row.entry_price,
            "stop_loss": row.stop_loss,
            "tp1": row.tp1,
            "tp2": row.tp2,
            "tp3": row.tp3,
            "tp1_hit": row.tp1_hit,
            "tp2_hit": row.tp2_hit,
            "tp3_hit": row.tp3_hit,
            "breakeven_set": row.breakeven_set,
            "position_size": row.position_size,
            "risk_amount": row.risk_amount,
            "pnl": row.pnl,
            "pnl_pct": row.pnl_pct,
            "confidence": row.confidence,
            "opened_at": row.opened_at.isoformat() if row.opened_at else None,
            "closed_at": row.closed_at.isoformat() if row.closed_at else None,
            "close_reason": row.close_reason,
            "broker_order_id": row.broker_order_id,
        }
