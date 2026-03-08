from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)  # forex | crypto
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(4))  # buy | sell
    mode: Mapped[str] = mapped_column(String(10))  # paper | live

    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    remaining_qty: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    hit_tp1: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_tp2: Mapped[bool] = mapped_column(Boolean, default=False)
    hit_tp3: Mapped[bool] = mapped_column(Boolean, default=False)
    moved_to_breakeven: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class TradeFeature(Base):
    __tablename__ = "trade_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    features: Mapped[dict] = mapped_column(JSON)
    label: Mapped[int] = mapped_column(Integer)  # 1 profitable / 0 unprofitable
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    balance: Mapped[float] = mapped_column(Float)
    equity: Mapped[float] = mapped_column(Float)
    drawdown: Mapped[float] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

