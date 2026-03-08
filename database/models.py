from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trade_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(10))       # "forex" | "crypto"
    direction: Mapped[str] = mapped_column(String(5))     # "long" | "short"
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    mode: Mapped[str] = mapped_column(String(10))         # "paper" | "live"

    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)

    lot_size: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float)
    atr_value: Mapped[float] = mapped_column(Float)

    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pips: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_signals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session: Mapped[str] = mapped_column(String(20), default="unknown")

    breakeven_moved: Mapped[bool] = mapped_column(Boolean, default=False)
    tp1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp3_hit: Mapped[bool] = mapped_column(Boolean, default=False)

    broker_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    open_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    open_trades: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(10))


class AIModelRecord(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    symbol: Mapped[str] = mapped_column(String(20))
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1_score: Mapped[float] = mapped_column(Float)
    n_samples: Mapped[int] = mapped_column(Integer)
    model_path: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SignalLog(Base):
    __tablename__ = "signal_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[str] = mapped_column(String(10))
    direction: Mapped[str] = mapped_column(String(5))
    timeframe: Mapped[str] = mapped_column(String(10))
    signal_type: Mapped[str] = mapped_column(String(50))
    h1_bias: Mapped[str] = mapped_column(String(10))
    m15_structure: Mapped[str] = mapped_column(String(20))
    bos_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    sweep_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    pullback_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    rejected_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(10))
    impact: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(256))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("event_time", "currency", "title", name="uq_news_event"),
    )
