from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.trade import TradeDirection, TradeStatus, Market


class TradeCreate(BaseModel):
    symbol: str
    market: Market
    direction: TradeDirection
    entry_price: float
    lot_size: float
    risk_amount: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr_value: Optional[float] = None
    confidence_score: Optional[float] = None
    signal_id: Optional[int] = None
    session_date: Optional[str] = None
    session_trade_number: Optional[int] = None


class TradeUpdate(BaseModel):
    status: Optional[TradeStatus] = None
    close_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    tp_hit: Optional[int] = None
    break_even_triggered: Optional[bool] = None
    broker_order_id: Optional[str] = None
    notes: Optional[str] = None
    stop_loss: Optional[float] = None


class TradeRead(BaseModel):
    id: int
    symbol: str
    market: Market
    direction: TradeDirection
    status: TradeStatus
    entry_price: float
    lot_size: float
    risk_amount: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr_value: Optional[float]
    broker_order_id: Optional[str]
    break_even_triggered: bool
    close_price: Optional[float]
    pnl: Optional[float]
    pnl_pct: Optional[float]
    tp_hit: Optional[int]
    confidence_score: Optional[float]
    signal_id: Optional[int]
    session_date: Optional[str]
    session_trade_number: Optional[int]
    created_at: datetime
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class TradeStats(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    best_trade: float
    worst_trade: float
    avg_confidence: float
