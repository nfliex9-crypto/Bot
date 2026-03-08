from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    side: Mapped[str] = mapped_column(String(6))
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    position_size: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    strategy_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    tp1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    break_even_moved: Mapped[bool] = mapped_column(Boolean, default=False)
    pnl: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
