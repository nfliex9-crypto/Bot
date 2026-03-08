from datetime import datetime

from pydantic import BaseModel


class TradeBase(BaseModel):
    market: str
    symbol: str
    side: str
    status: str
    session_name: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    quantity: float
    confidence: float
    risk_percent: float
    atr_value: float
    pnl: float


class TradeRead(TradeBase):
    id: int
    opened_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class TradeListResponse(BaseModel):
    items: list[TradeRead]
