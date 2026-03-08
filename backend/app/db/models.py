from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class MarketType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class OrderSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class RecordStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    SIMULATED = "simulated"


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[MarketType] = mapped_column(SqlEnum(MarketType), index=True)
    timeframe: Mapped[str] = mapped_column(String(10), default="M15")
    side: Mapped[OrderSide] = mapped_column(SqlEnum(OrderSide), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    status: Mapped[RecordStatus] = mapped_column(SqlEnum(RecordStatus), default=RecordStatus.PENDING)
    rationale: Mapped[str] = mapped_column(Text)
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    trades: Mapped[list["Trade"]] = relationship(back_populates="signal")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market: Mapped[MarketType] = mapped_column(SqlEnum(MarketType), index=True)
    side: Mapped[OrderSide] = mapped_column(SqlEnum(OrderSide), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    broker: Mapped[str] = mapped_column(String(30))
    execution_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[RecordStatus] = mapped_column(SqlEnum(RecordStatus), default=RecordStatus.PENDING)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    highest_tp_hit: Mapped[int] = mapped_column(Integer, default=0)
    break_even_armed: Mapped[bool] = mapped_column(default=False)
    session_name: Mapped[str] = mapped_column(String(30), default="London")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    signal: Mapped[Signal | None] = relationship(back_populates="trades")


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    open_risk: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
