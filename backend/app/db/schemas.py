from datetime import datetime

from pydantic import BaseModel


class SignalOut(BaseModel):
    id: int
    market: str
    symbol: str
    side: str
    confidence: float
    strategy_score: float
    reason: str
    executed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TradeOut(BaseModel):
    id: int
    market: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    risk_amount: float
    status: str
    broker_order_id: str | None
    session_id: str
    pnl: float
    opened_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True


class EquityOut(BaseModel):
    id: int
    equity: float
    drawdown: float
    session_id: str
    created_at: datetime

    class Config:
        from_attributes = True
