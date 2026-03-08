from datetime import datetime

from pydantic import BaseModel


class SignalRead(BaseModel):
    id: int
    market: str
    symbol: str
    side: str
    timeframe: str
    signal_type: str
    status: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    atr_value: float
    executed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SignalListResponse(BaseModel):
    items: list[SignalRead]


class RunSignalRequest(BaseModel):
    market: str = "forex"
    symbol: str = "EURUSD"
    timeframe: str = "M15"


class RunSignalResponse(BaseModel):
    message: str
    signal_id: int | None = None
    trade_id: int | None = None
