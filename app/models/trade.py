from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum as SAEnum, Text, JSON
from sqlalchemy.sql import func
from app.database import Base
import enum


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class TradeDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    ticket = Column(String(64), unique=True, index=True, nullable=True)

    # Symbol and market
    symbol = Column(String(20), nullable=False, index=True)
    market_type = Column(String(10), nullable=False)  # forex | crypto

    # Direction
    direction = Column(SAEnum(TradeDirection), nullable=False)

    # Status
    status = Column(SAEnum(TradeStatus), default=TradeStatus.PENDING, index=True)

    # Trading mode
    trading_mode = Column(String(10), nullable=False, default="paper")

    # Entry / exit
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)

    # Lot size
    lot_size = Column(Float, nullable=False)

    # Stop loss and take profits
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)

    # ATR at entry
    atr_at_entry = Column(Float, nullable=True)

    # Risk metrics
    risk_amount = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)

    # P&L
    pnl = Column(Float, default=0.0)
    pnl_pips = Column(Float, default=0.0)

    # Break-even
    breakeven_moved = Column(Boolean, default=False)
    breakeven_price = Column(Float, nullable=True)

    # TP hits
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)

    # Session info
    session = Column(String(20), nullable=True)  # london | new_york | overlap

    # AI confidence
    ai_confidence = Column(Float, nullable=True)
    signal_id = Column(Integer, nullable=True, index=True)

    # Strategy info
    strategy = Column(String(50), nullable=True)
    timeframe = Column(String(10), nullable=True)
    setup_notes = Column(Text, nullable=True)

    # Extra metadata
    meta_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    opened_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Trade {self.symbol} {self.direction} @ {self.entry_price} [{self.status}]>"
