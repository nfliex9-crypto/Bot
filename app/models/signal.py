from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum as SAEnum, Text, JSON
from sqlalchemy.sql import func
from app.database import Base
import enum


class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)

    symbol = Column(String(20), nullable=False, index=True)
    market_type = Column(String(10), nullable=False)

    direction = Column(String(10), nullable=False)  # long | short
    status = Column(SAEnum(SignalStatus), default=SignalStatus.PENDING, index=True)

    # Prices at signal generation
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)

    # ATR
    atr = Column(Float, nullable=True)

    # Timeframes
    h1_bias = Column(String(10), nullable=True)   # bullish | bearish | neutral
    m15_trend = Column(String(10), nullable=True)
    m5_signal = Column(String(10), nullable=True)

    # Strategy components
    liquidity_sweep_detected = Column(Boolean, default=False)
    bos_detected = Column(Boolean, default=False)
    pullback_entry = Column(Boolean, default=False)

    # AI scoring
    ai_confidence = Column(Float, nullable=True)
    ai_features = Column(JSON, nullable=True)

    # Rejection reason
    rejection_reason = Column(Text, nullable=True)

    # Session
    session = Column(String(20), nullable=True)

    # News clear
    news_clear = Column(Boolean, default=True)

    # Risk/Reward
    risk_reward = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Signal {self.symbol} {self.direction} [{self.status}] conf={self.ai_confidence}>"
