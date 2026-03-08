from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON

from database.connection import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class TradeRecordDB(Base):
    __tablename__ = "trades"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    signal_id = Column(String(36), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    entry_price = Column(Float, default=0.0)
    stop_loss = Column(Float, default=0.0)
    tp1 = Column(Float, default=0.0)
    tp2 = Column(Float, default=0.0)
    tp3 = Column(Float, default=0.0)
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    breakeven_set = Column(Boolean, default=False)
    position_size = Column(Float, default=0.0)
    risk_amount = Column(Float, default=0.0)
    pnl = Column(Float, default=0.0)
    pnl_pct = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    close_reason = Column(String(100), default="")
    broker_order_id = Column(String(100), default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_trades_status_symbol", "status", "symbol"),
        Index("ix_trades_opened_at", "opened_at"),
    )


class CandleDB(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(5), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)

    __table_args__ = (
        Index("ix_candles_sym_tf_ts", "symbol", "timeframe", "timestamp", unique=True),
    )


class SignalLogDB(Base):
    __tablename__ = "signal_log"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    symbol = Column(String(20), nullable=False)
    market = Column(String(10), nullable=False)
    direction = Column(String(10), nullable=False)
    signal_type = Column(String(30), nullable=False)
    entry_price = Column(Float, default=0.0)
    stop_loss = Column(Float, default=0.0)
    tp1 = Column(Float, default=0.0)
    tp2 = Column(Float, default=0.0)
    tp3 = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    accepted = Column(Boolean, default=False)
    reject_reason = Column(String(200), default="")
    features_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class AccountSnapshotDB(Base):
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    balance = Column(Float, nullable=False)
    equity = Column(Float, nullable=False)
    open_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    current_drawdown_pct = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    session_trades = Column(Integer, default=0)
    snapshot_at = Column(DateTime, default=datetime.utcnow, index=True)


class AIModelMetricDB(Base):
    __tablename__ = "ai_model_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    accuracy = Column(Float, default=0.0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)
    feature_importances = Column(JSON, default=dict)
    training_samples = Column(Integer, default=0)
    trained_at = Column(DateTime, default=datetime.utcnow)
