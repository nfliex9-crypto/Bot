from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Numeric, Boolean, Integer, DateTime, Text, JSON,
    Enum as SAEnum, ForeignKey, UniqueConstraint, Index, func
)
from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid
import enum

from config.settings import settings


class TradeStatus(str, enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL_CLOSE = "partial_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeDirection(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class MarketType(str, enum.Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class TradingMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class SignalStatus(str, enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CloseReason(str, enum.Enum):
    TP1 = "tp1"
    TP2 = "tp2"
    TP3 = "tp3"
    STOP_LOSS = "stop_loss"
    BREAK_EVEN = "break_even"
    MANUAL = "manual"
    MAX_DRAWDOWN = "max_drawdown"
    SESSION_END = "session_end"
    NEWS_FILTER = "news_filter"


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[MarketType] = mapped_column(SAEnum(MarketType), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(SAEnum(TradeDirection), nullable=False)
    status: Mapped[TradeStatus] = mapped_column(SAEnum(TradeStatus), default=TradeStatus.PENDING)
    mode: Mapped[TradingMode] = mapped_column(SAEnum(TradingMode), default=TradingMode.PAPER)

    entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    stop_loss: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tp1: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tp2: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    tp3: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    break_even_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))

    lot_size: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    risk_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    account_balance_at_open: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))

    ai_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    signal_id: Mapped[Optional[uuid.UUID]] = mapped_column()

    broker_ticket: Mapped[Optional[str]] = mapped_column(String(50))

    open_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    close_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[Optional[CloseReason]] = mapped_column(SAEnum(CloseReason))

    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    max_favorable_excursion: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    max_adverse_excursion: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[MarketType] = mapped_column(SAEnum(MarketType), nullable=False)
    direction: Mapped[TradeDirection] = mapped_column(SAEnum(TradeDirection), nullable=False)
    status: Mapped[SignalStatus] = mapped_column(SAEnum(SignalStatus), default=SignalStatus.PENDING)

    htf_bias: Mapped[Optional[str]] = mapped_column(String(10))
    mtf_trend: Mapped[Optional[str]] = mapped_column(String(10))
    ltf_entry: Mapped[Optional[str]] = mapped_column(String(10))

    liquidity_swept: Mapped[bool] = mapped_column(Boolean, default=False)
    bos_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    pullback_valid: Mapped[bool] = mapped_column(Boolean, default=False)

    entry_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    tp1: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    tp2: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    tp3: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))
    atr_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8))

    ai_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    ai_features: Mapped[dict] = mapped_column(JSON, default=dict)

    session: Mapped[Optional[str]] = mapped_column(String(20))
    news_clear: Mapped[bool] = mapped_column(Boolean, default=True)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "open_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    market: Mapped[MarketType] = mapped_column(SAEnum(MarketType), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    mode: Mapped[TradingMode] = mapped_column(SAEnum(TradingMode), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    equity: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    open_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    win_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    profit_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    sharpe_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class NewsEvent(Base):
    __tablename__ = "news_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(10))
    impact: Mapped[str] = mapped_column(String(10), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual: Mapped[Optional[str]] = mapped_column(String(50))
    forecast: Mapped[Optional[str]] = mapped_column(String(50))
    previous: Mapped[Optional[str]] = mapped_column(String(50))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotSession(Base):
    __tablename__ = "bot_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mode: Mapped[TradingMode] = mapped_column(SAEnum(TradingMode), nullable=False)
    trades_taken: Mapped[int] = mapped_column(Integer, default=0)
    session_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


# ── Database Engine ───────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
