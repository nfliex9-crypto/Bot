from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import BotState, EconomicEventRecord, TradeRecord
from app.domain.models import EconomicEvent, MarketType, OpenTrade, SizedTradeSignal, TradeSide, TradingMode
from app.execution.base import BrokerOrderResult


class TradingRepository:
    def __init__(self, session_factory: sessionmaker, engine) -> None:
        self.session_factory = session_factory
        self.engine = engine

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        with self.session_factory() as session:
            state = session.get(BotState, 1)
            if state is None:
                session.add(BotState(id=1, enabled=True, mode="paper"))
                session.commit()

    def get_bot_state(self) -> BotState:
        with self.session_factory() as session:
            state = session.get(BotState, 1)
            if state is None:
                state = BotState(id=1, enabled=True, mode="paper")
                session.add(state)
                session.commit()
                session.refresh(state)
            return state

    def set_bot_enabled(self, enabled: bool) -> BotState:
        with self.session_factory() as session:
            state = session.get(BotState, 1) or BotState(id=1)
            state.enabled = enabled
            session.add(state)
            session.commit()
            session.refresh(state)
            return state

    def set_bot_mode(self, mode: TradingMode) -> BotState:
        with self.session_factory() as session:
            state = session.get(BotState, 1) or BotState(id=1)
            state.mode = mode.value
            session.add(state)
            session.commit()
            session.refresh(state)
            return state

    def touch_heartbeat(self, error: str | None = None) -> None:
        with self.session_factory() as session:
            state = session.get(BotState, 1) or BotState(id=1)
            state.heartbeat_at = datetime.now(UTC)
            state.last_error = error
            session.add(state)
            session.commit()

    def replace_events(self, events: list[EconomicEvent]) -> int:
        with self.session_factory() as session:
            session.query(EconomicEventRecord).delete()
            for event in events:
                session.add(
                    EconomicEventRecord(
                        title=event.title,
                        currency=event.currency,
                        impact=event.impact,
                        starts_at=event.starts_at,
                        source=event.source,
                    )
                )
            session.commit()
            return len(events)

    def list_events(self) -> list[EconomicEvent]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(EconomicEventRecord).order_by(EconomicEventRecord.starts_at.asc())
            ).all()
            return [
                EconomicEvent(
                    title=row.title,
                    currency=row.currency,
                    impact=row.impact,
                    starts_at=row.starts_at,
                    source=row.source,
                )
                for row in rows
            ]

    def create_trade(
        self,
        signal: SizedTradeSignal,
        mode: TradingMode,
        order_result: BrokerOrderResult,
    ) -> OpenTrade:
        trade_id = uuid4().hex
        with self.session_factory() as session:
            row = TradeRecord(
                id=trade_id,
                broker_trade_id=order_result.broker_trade_id,
                symbol=signal.symbol,
                market=signal.market.value,
                side=signal.side.value,
                mode=mode.value,
                status="open",
                entry_price=order_result.fill_price,
                stop_loss=signal.stop_loss,
                take_profit_1=signal.take_profit_1,
                take_profit_2=signal.take_profit_2,
                take_profit_3=signal.take_profit_3,
                position_size=signal.position_size,
                remaining_size=signal.position_size,
                confidence=signal.confidence,
                metadata_json=signal.metadata,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_open_trade(row)

    def list_open_trades(self) -> list[OpenTrade]:
        with self.session_factory() as session:
            rows = session.scalars(select(TradeRecord).where(TradeRecord.status == "open")).all()
            return [self._to_open_trade(row) for row in rows]

    def list_recent_trades(self, limit: int = 50) -> list[TradeRecord]:
        with self.session_factory() as session:
            return session.scalars(
                select(TradeRecord).order_by(TradeRecord.created_at.desc()).limit(limit)
            ).all()

    def count_open_trades_for_symbol(self, symbol: str) -> int:
        with self.session_factory() as session:
            rows = session.scalars(
                select(TradeRecord).where(TradeRecord.symbol == symbol, TradeRecord.status == "open")
            ).all()
            return len(rows)

    def count_session_trades(self, market: MarketType) -> int:
        session_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session_factory() as session:
            rows = session.scalars(
                select(TradeRecord).where(
                    TradeRecord.market == market.value,
                    TradeRecord.created_at >= session_start,
                )
            ).all()
            return len(rows)

    def mark_tp(self, trade_id: str, tp_number: int, remaining_size: float, realized_pnl_delta: float) -> OpenTrade:
        with self.session_factory() as session:
            row = session.get(TradeRecord, trade_id)
            if row is None:
                raise KeyError(f"Trade {trade_id} not found")
            if tp_number == 1:
                row.tp1_hit = True
                row.break_even_moved = True
            elif tp_number == 2:
                row.tp2_hit = True
            elif tp_number == 3:
                row.tp3_hit = True
            row.remaining_size = remaining_size
            row.realized_pnl += realized_pnl_delta
            if remaining_size <= 0:
                row.status = "closed"
                row.closed_at = datetime.now(UTC)
            session.commit()
            session.refresh(row)
            return self._to_open_trade(row)

    def close_trade(self, trade_id: str, remaining_size: float, realized_pnl_delta: float, reason: str) -> None:
        with self.session_factory() as session:
            row = session.get(TradeRecord, trade_id)
            if row is None:
                raise KeyError(f"Trade {trade_id} not found")
            row.remaining_size = remaining_size
            row.realized_pnl += realized_pnl_delta
            row.status = "closed"
            row.closed_at = datetime.now(UTC)
            row.notes = reason
            session.commit()

    def update_stop(self, trade_id: str, stop_loss: float, break_even_moved: bool) -> None:
        with self.session_factory() as session:
            row = session.get(TradeRecord, trade_id)
            if row is None:
                raise KeyError(f"Trade {trade_id} not found")
            row.stop_loss = stop_loss
            row.break_even_moved = break_even_moved
            session.commit()

    def _to_open_trade(self, row: TradeRecord) -> OpenTrade:
        return OpenTrade(
            trade_id=row.id,
            symbol=row.symbol,
            market=MarketType(row.market),
            side=TradeSide(row.side),
            entry_price=row.entry_price,
            stop_loss=row.stop_loss,
            take_profit_1=row.take_profit_1,
            take_profit_2=row.take_profit_2,
            take_profit_3=row.take_profit_3,
            position_size=row.position_size,
            remaining_size=row.remaining_size,
            confidence=row.confidence,
            mode=TradingMode(row.mode),
            tp1_hit=row.tp1_hit,
            tp2_hit=row.tp2_hit,
            tp3_hit=row.tp3_hit,
            break_even_moved=row.break_even_moved,
            broker_trade_id=row.broker_trade_id,
            metadata=row.metadata_json or {},
        )
