from datetime import datetime

from pydantic import BaseModel


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    balance: float
    drawdown: float


class EquityResponse(BaseModel):
    current_equity: float
    current_balance: float
    max_drawdown: float
    points: list[EquityPoint]
