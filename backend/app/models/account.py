from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean
from sqlalchemy.sql import func
import enum
from app.database import Base


class BrokerType(str, enum.Enum):
    MT5 = "MT5"
    BINANCE = "BINANCE"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    broker = Column(Enum(BrokerType), nullable=False)
    account_name = Column(String(100))
    account_id = Column(String(100))
    is_active = Column(Boolean, default=True)

    initial_balance = Column(Float, nullable=False)
    current_balance = Column(Float, nullable=False)
    equity = Column(Float)
    margin_used = Column(Float, default=0.0)

    peak_equity = Column(Float)
    current_drawdown_pct = Column(Float, default=0.0)
    max_drawdown_pct = Column(Float, default=0.0)

    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)

    session_trades_today = Column(Integer, default=0)
    session_date = Column(String(10))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    broker = Column(String(10))
    equity = Column(Float, nullable=False)
    balance = Column(Float, nullable=False)
    drawdown_pct = Column(Float, default=0.0)
    open_trades = Column(Integer, default=0)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
