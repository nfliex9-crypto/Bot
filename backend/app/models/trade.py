from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, Text
from sqlalchemy.sql import func
import enum
from app.database import Base


class TradeDirection(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, enum.Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    BREAKEVEN = "BREAKEVEN"


class Market(str, enum.Enum):
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(Enum(Market), nullable=False)
    direction = Column(Enum(TradeDirection), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING, index=True)

    # Entry
    entry_price = Column(Float, nullable=False)
    lot_size = Column(Float, nullable=False)
    risk_amount = Column(Float, nullable=False)

    # Stop Loss & Take Profits
    stop_loss = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    atr_value = Column(Float)

    # Execution
    broker_order_id = Column(String(100))
    break_even_triggered = Column(Boolean, default=False)

    # Result
    close_price = Column(Float)
    pnl = Column(Float)
    pnl_pct = Column(Float)
    tp_hit = Column(Integer)  # 1, 2, or 3

    # AI
    confidence_score = Column(Float)
    signal_id = Column(Integer, index=True)

    # Session
    session_date = Column(String(10))
    session_trade_number = Column(Integer)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    opened_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))

    notes = Column(Text)
