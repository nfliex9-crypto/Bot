from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from app.models.signal import SignalStatus


class SignalCreate(BaseModel):
    symbol: str
    market_type: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    atr: Optional[float] = None
    h1_bias: Optional[str] = None
    m15_trend: Optional[str] = None
    m5_signal: Optional[str] = None
    liquidity_sweep_detected: bool = False
    bos_detected: bool = False
    pullback_entry: bool = False
    ai_confidence: Optional[float] = None
    ai_features: Optional[Dict[str, Any]] = None
    session: Optional[str] = None
    news_clear: bool = True
    risk_reward: Optional[float] = None


class SignalResponse(BaseModel):
    id: int
    symbol: str
    market_type: str
    direction: str
    status: SignalStatus
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    atr: Optional[float]
    h1_bias: Optional[str]
    m15_trend: Optional[str]
    m5_signal: Optional[str]
    liquidity_sweep_detected: bool
    bos_detected: bool
    pullback_entry: bool
    ai_confidence: Optional[float]
    session: Optional[str]
    news_clear: bool
    risk_reward: Optional[float]
    rejection_reason: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]

    model_config = {"from_attributes": True}
