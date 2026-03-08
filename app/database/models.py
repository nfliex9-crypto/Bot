"""SQLAlchemy models for PostgreSQL."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Trade(Base):
    """Record of executed trades."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(128), unique=True, nullable=False)
    symbol = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)  # long, short
    strategy = Column(String(32), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    market_type = Column(String(16), nullable=False)  # forex, crypto
    paper = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default="open")  # open, closed, partial
    pnl = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(Text, nullable=True)


class SignalLog(Base):
    """Log of generated signals (for ML training)."""
    __tablename__ = "signal_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False)
    direction = Column(String(8), nullable=False)
    strategy = Column(String(32), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    executed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    features_json = Column(Text, nullable=True)


class SystemState(Base):
    """Persistent system state (session counts, etc.)."""
    __tablename__ = "system_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(64), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
