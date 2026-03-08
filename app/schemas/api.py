from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    mode: str
    running: bool
    timestamp: datetime


class BotStatusResponse(BaseModel):
    running: bool
    mode: str
    equity: float
    drawdown_pct: float
    open_trades: int
    last_cycle_timestamp: datetime | None
    last_cycle_notes: list[str]


class BotControlRequest(BaseModel):
    running: bool

