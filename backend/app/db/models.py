import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, Text, Enum, ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base
import enum


class MarketType(str, enum.Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class SignalStatus(str, enum.Enum):
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    REJECTED = "rejected"


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    trades = relationship("Trade", back_populates="user")
    signals = relationship("Signal", back_populates="user")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    market_type = Column(Enum(MarketType), nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)

    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float)
    take_profit_2 = Column(Float)
    take_profit_3 = Column(Float)
    break_even_triggered = Column(Boolean, default=False)

    lot_size = Column(Float, nullable=False)
    risk_amount = Column(Float)
    risk_percent = Column(Float)

    exit_price = Column(Float)
    pnl = Column(Float)
    pnl_percent = Column(Float)

    ai_confidence = Column(Float)
    strategy_name = Column(String(100))
    signal_id = Column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)

    external_order_id = Column(String(100))
    broker_data = Column(JSON)

    opened_at = Column(DateTime(timezone=True), default=utcnow)
    closed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="trades")
    signal = relationship("Signal", back_populates="trades")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    market_type = Column(Enum(MarketType), nullable=False)
    side = Column(Enum(OrderSide), nullable=False)
    status = Column(Enum(SignalStatus), default=SignalStatus.ACTIVE)

    entry_zone_low = Column(Float)
    entry_zone_high = Column(Float)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float)
    take_profit_2 = Column(Float)
    take_profit_3 = Column(Float)

    ai_confidence = Column(Float, nullable=False)
    strategy_name = Column(String(100))
    strategy_details = Column(JSON)

    timeframe = Column(String(10))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    expires_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="signals")
    trades = relationship("Trade", back_populates="signal")


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    drawdown = Column(Float, default=0.0)
    drawdown_percent = Column(Float, default=0.0)
    peak_equity = Column(Float)
    open_trades = Column(Integer, default=0)
    timestamp = Column(DateTime(timezone=True), default=utcnow)


class MarketData(Base):
    __tablename__ = "market_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    market_type = Column(Enum(MarketType), nullable=False)
    timeframe = Column(String(10), nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    class Config:
        unique_together = ("symbol", "timeframe", "timestamp")


class AIModelMetrics(Base):
    __tablename__ = "ai_model_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version = Column(String(50), nullable=False)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    total_predictions = Column(Integer, default=0)
    correct_predictions = Column(Integer, default=0)
    feature_importance = Column(JSON)
    training_data_size = Column(Integer)
    trained_at = Column(DateTime(timezone=True), default=utcnow)
    created_at = Column(DateTime(timezone=True), default=utcnow)
