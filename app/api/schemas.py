from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class EngineStatusResponse(BaseModel):
    running: bool
    mode: Literal["paper", "live"]
    active_positions: int
    trades_today: int
    last_cycle_at: datetime | None


class StartEngineRequest(BaseModel):
    mode: Literal["paper", "live"] = "paper"


class SignalResponse(BaseModel):
    symbol: str
    market: str
    side: str
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
