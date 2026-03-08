from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MarketRequest(BaseModel):
    market: Literal["forex", "crypto"]
    symbol: str
    timeframe: str = "M15"
    bars: int = Field(default=300, ge=100, le=5000)
    session_id: str = "default"
    equity: float = Field(default=10000.0, gt=0)


class Signal(BaseModel):
    direction: Literal["buy", "sell", "none"]
    liquidity_sweep: bool
    break_of_structure: bool
    pullback_entry: bool
    reason: str


class RiskPlan(BaseModel):
    allowed: bool
    reason: str
    position_size: float = 0.0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0


class TradeDecision(BaseModel):
    signal: Signal
    confidence: float
    risk_plan: RiskPlan


class TradeRecordOut(BaseModel):
    id: int
    market: str
    symbol: str
    side: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    position_size: float
    confidence: float
    strategy_reason: str
    status: str
    tp1_hit: bool
    break_even_moved: bool
    pnl: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float


class DashboardPayload(BaseModel):
    equity: list[EquityPoint]
    trade_history: list[TradeRecordOut]
    ai_confidence: float
    live_signal: Signal
