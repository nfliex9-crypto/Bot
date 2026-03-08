from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BotStatusResponse(BaseModel):
    running: bool
    mode: str
    active_session: str | None = None
    last_cycle_at: datetime | None = None
    daily_drawdown: float = 0.0
    open_positions: int = 0


class TradeResponse(BaseModel):
    id: int
    symbol: str
    market: str
    direction: str
    status: str
    mode: str
    session: str
    entry_price: float
    stop_loss: float
    take_profit_levels: list[float]
    quantity: float
    remaining_quantity: float
    risk_amount: float
    confidence: float
    realized_pnl: float
    opened_at: datetime
    closed_at: datetime | None


class SignalResponse(BaseModel):
    id: int
    symbol: str
    market: str
    direction: str
    reason: str
    h1_bias: str
    m15_trend: str
    session: str
    entry_price: float
    stop_loss: float
    take_profit_levels: list[float]
    atr: float
    confidence: float
    created_at: datetime


class RunOnceResponse(BaseModel):
    evaluated_symbols: int = Field(..., ge=0)
    opened_trades: int = Field(..., ge=0)
    blocked_by_filters: int = Field(..., ge=0)
