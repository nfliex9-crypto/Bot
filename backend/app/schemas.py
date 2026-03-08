from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import MarketType, OrderSide, RecordStatus


class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    market: MarketType
    timeframe: str
    side: OrderSide
    confidence: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    status: RecordStatus
    rationale: str
    features: dict
    created_at: datetime


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: int | None
    symbol: str
    market: MarketType
    side: OrderSide
    quantity: float
    risk_amount: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    broker: str
    execution_id: str | None
    status: RecordStatus
    pnl: float
    highest_tp_hit: int
    break_even_armed: bool
    session_name: str
    meta: dict
    opened_at: datetime
    closed_at: datetime | None


class EquitySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    balance: float
    equity: float
    drawdown: float
    open_risk: float
    created_at: datetime


class DashboardOverview(BaseModel):
    latest_equity: EquitySnapshotResponse | None
    live_signals: list[SignalResponse]
    recent_trades: list[TradeResponse]
    win_rate: float
    total_pnl: float


class RunCycleResponse(BaseModel):
    processed_symbols: int
    generated_signals: int
    executed_trades: int
    rejected_trades: int
