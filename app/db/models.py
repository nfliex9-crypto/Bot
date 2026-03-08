from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    market: Mapped[str] = mapped_column(String(20), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), index=True)
    session_label: Mapped[str] = mapped_column(String(30), index=True)
    venue: Mapped[str] = mapped_column(String(30))
    provider_order_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    entry_price: Mapped[float] = mapped_column(Float)
    executed_price: Mapped[float] = mapped_column(Float)
    initial_stop_loss: Mapped[float] = mapped_column(Float)
    current_stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)

    requested_quantity: Mapped[float] = mapped_column(Float)
    executed_quantity: Mapped[float] = mapped_column(Float)
    remaining_quantity: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)
    strategy_score: Mapped[float] = mapped_column(Float)
    ai_confidence: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    structure_level: Mapped[float] = mapped_column(Float)
    atr_value: Mapped[float] = mapped_column(Float)

    break_even_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    tp1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp3_hit: Mapped[bool] = mapped_column(Boolean, default=False)

    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)

    rationale: Mapped[list[str]] = mapped_column(JSON, default=list)
    feature_vector: Mapped[dict[str, float | int | bool | str]] = mapped_column(JSON, default=dict)
    details: Mapped[dict[str, float | int | bool | str]] = mapped_column(JSON, default=dict)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SignalRecord(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    market: Mapped[str] = mapped_column(String(20), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_score: Mapped[float] = mapped_column(Float, default=0.0)
    passed_filters: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rationale: Mapped[list[str]] = mapped_column(JSON, default=list)
    payload: Mapped[dict[str, float | int | bool | str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BotState(Base):
    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    trading_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    current_equity: Mapped[float] = mapped_column(Float, default=3000.0)
    peak_equity: Mapped[float] = mapped_column(Float, default=3000.0)
    current_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    last_cycle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
