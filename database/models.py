"""
SQLAlchemy ORM models for the PostgreSQL database.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(50), unique=True, nullable=False, index=True)
    signal_id = Column(String(50), index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10))
    direction = Column(String(10))
    entry_price = Column(Float)
    stop_loss = Column(Float)
    tp1 = Column(Float)
    tp2 = Column(Float)
    tp3 = Column(Float)
    position_size = Column(Float)
    status = Column(String(20), index=True)
    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    confidence = Column(Float)
    ai_score = Column(Float)
    risk_reward = Column(Float)
    reason = Column(Text)
    market_bias = Column(String(20))
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    broker_order_id = Column(String(100))
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    breakeven_set = Column(Boolean, default=False)
    metadata_json = Column(Text)


class SignalRecord(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    direction = Column(String(10))
    entry_price = Column(Float)
    stop_loss = Column(Float)
    tp1 = Column(Float)
    tp2 = Column(Float)
    tp3 = Column(Float)
    confidence = Column(Float)
    ai_score = Column(Float)
    strength = Column(String(20))
    market_bias = Column(String(20))
    reason = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    executed = Column(Boolean, default=False)
    rejected_reason = Column(Text, nullable=True)


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    balance = Column(Float)
    equity = Column(Float)
    drawdown = Column(Float)
    open_trades = Column(Integer)
    daily_pnl = Column(Float)
    total_trades = Column(Integer)
    win_rate = Column(Float)


class MLTrainingData(Base):
    __tablename__ = "ml_training_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(50), index=True)
    features_json = Column(Text)
    label = Column(Integer)  # 1=win, 0=loss
    timestamp = Column(DateTime, default=datetime.utcnow)
