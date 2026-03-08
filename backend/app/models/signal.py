from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, JSON, Text
from sqlalchemy.sql import func
import enum
from app.database import Base


class SignalStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    timeframe = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)
    status = Column(Enum(SignalStatus), default=SignalStatus.ACTIVE, index=True)

    # Price levels
    entry_zone_low = Column(Float)
    entry_zone_high = Column(Float)
    stop_loss = Column(Float)
    tp1 = Column(Float)
    tp2 = Column(Float)
    tp3 = Column(Float)

    # Strategy components
    liquidity_sweep_detected = Column(Boolean, default=False)
    bos_detected = Column(Boolean, default=False)
    pullback_confirmed = Column(Boolean, default=False)
    sweep_level = Column(Float)
    bos_level = Column(Float)

    # ATR
    atr_value = Column(Float)

    # AI scoring
    confidence_score = Column(Float)
    feature_importance = Column(JSON)
    model_version = Column(String(20))

    # Context
    market_structure = Column(String(50))
    session = Column(String(20))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    executed_at = Column(DateTime(timezone=True))
