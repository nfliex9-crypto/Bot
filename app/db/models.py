from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market_type: Mapped[str] = mapped_column(String(10), index=True)  # forex | crypto
    side: Mapped[str] = mapped_column(String(5))  # buy | sell
    mode: Mapped[str] = mapped_column(String(10))  # paper | live
    status: Mapped[str] = mapped_column(String(20), default="open")

    confidence: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    position_size: Mapped[float] = mapped_column(Float)
    risk_amount: Mapped[float] = mapped_column(Float)

    execution_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    tp1_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp2_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    tp3_hit: Mapped[bool] = mapped_column(Boolean, default=False)

    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BotState(Base):
    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    running: Mapped[bool] = mapped_column(Boolean, default=True)
    current_equity: Mapped[float] = mapped_column(Float, default=3000.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

