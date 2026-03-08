from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str
    mode: str
    uptime_seconds: float
    balance: float
    equity: float
    open_trades: int
    session_trades: int
    drawdown_pct: float
    current_session: dict


class TradeResponse(BaseModel):
    id: int
    symbol: str
    market: str
    side: str
    status: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    quantity: float
    confidence: float
    pnl: Optional[float] = None
    is_paper: bool
    opened_at: datetime
    closed_at: Optional[datetime] = None


class SignalResponse(BaseModel):
    id: int
    symbol: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    created_at: datetime


class PerformanceResponse(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_drawdown: float
    profit_factor: float
    avg_rr: float
    best_trade: float
    worst_trade: float


class AIModelResponse(BaseModel):
    model_loaded: bool
    feature_importance: dict
    min_confidence: float
    total_predictions: int


class HealthResponse(BaseModel):
    status: str
    database: str
    mt5_connected: bool
    binance_connected: bool
    timestamp: datetime
