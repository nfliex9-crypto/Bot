from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.trade import TradeStatus, TradeDirection


class TradeCreate(BaseModel):
    symbol: str
    market_type: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    lot_size: float
    atr_at_entry: Optional[float] = None
    risk_amount: Optional[float] = None
    ai_confidence: Optional[float] = None
    signal_id: Optional[int] = None
    strategy: Optional[str] = None
    session: Optional[str] = None
    setup_notes: Optional[str] = None
    trading_mode: str = "paper"


class TradeUpdate(BaseModel):
    status: Optional[TradeStatus] = None
    current_price: Optional[float] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pips: Optional[float] = None
    breakeven_moved: Optional[bool] = None
    tp1_hit: Optional[bool] = None
    tp2_hit: Optional[bool] = None
    tp3_hit: Optional[bool] = None


class TradeResponse(BaseModel):
    id: int
    ticket: Optional[str]
    symbol: str
    market_type: str
    direction: TradeDirection
    status: TradeStatus
    trading_mode: str
    entry_price: float
    current_price: Optional[float]
    exit_price: Optional[float]
    lot_size: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    atr_at_entry: Optional[float]
    risk_amount: Optional[float]
    risk_reward_ratio: Optional[float]
    pnl: float
    pnl_pips: float
    breakeven_moved: bool
    tp1_hit: bool
    tp2_hit: bool
    tp3_hit: bool
    session: Optional[str]
    ai_confidence: Optional[float]
    strategy: Optional[str]
    created_at: datetime
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]

    model_config = {"from_attributes": True}
