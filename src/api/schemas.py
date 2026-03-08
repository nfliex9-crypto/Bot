from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from enum import Enum


class TradeStatusEnum(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL_CLOSE = "partial_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradeDirectionEnum(str, Enum):
    LONG = "long"
    SHORT = "short"


class MarketTypeEnum(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


# ── Response Schemas ──────────────────────────────────────────────────────────

class TradeResponse(BaseModel):
    id: UUID
    symbol: str
    market: MarketTypeEnum
    direction: TradeDirectionEnum
    status: TradeStatusEnum
    mode: str
    entry_price: Optional[float]
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    break_even_price: Optional[float]
    lot_size: float
    risk_amount: float
    ai_confidence: Optional[float]
    broker_ticket: Optional[str]
    open_time: Optional[datetime]
    close_time: Optional[datetime]
    close_reason: Optional[str]
    realized_pnl: float
    created_at: datetime

    class Config:
        from_attributes = True


class PerformanceResponse(BaseModel):
    balance: float
    equity: float
    open_trades: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: Optional[float]
    profit_factor: Optional[float]
    max_drawdown: float
    session_trades: int
    current_drawdown_pct: float


class BotStatusResponse(BaseModel):
    running: bool
    mode: str
    uptime_seconds: float
    last_scan: Optional[datetime]
    active_symbols: List[str]
    session_info: Dict[str, Any]
    ai_status: Dict[str, Any]
    risk_status: Dict[str, Any]


class SignalResponse(BaseModel):
    id: UUID
    symbol: str
    market: str
    direction: str
    status: str
    htf_bias: Optional[str]
    mtf_trend: Optional[str]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    tp1: Optional[float]
    ai_confidence: Optional[float]
    session: Optional[str]
    news_clear: bool
    generated_at: datetime

    class Config:
        from_attributes = True


class NewsEventResponse(BaseModel):
    title: str
    currency: Optional[str]
    impact: str
    event_time: datetime
    minutes_until: int


class ManualTradeRequest(BaseModel):
    symbol: str = Field(..., description="Trading symbol, e.g. EURUSD or BTCUSDT")
    direction: TradeDirectionEnum
    entry_price: Optional[float] = None
    stop_loss: float
    tp1: float
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    lot_size: Optional[float] = None
    comment: str = "MANUAL"


class BotControlRequest(BaseModel):
    action: str = Field(..., description="start | stop | pause | resume | retrain_ai")


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: str
    trading_mode: str
