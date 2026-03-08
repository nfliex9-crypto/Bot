from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.account import BrokerType


class AccountRead(BaseModel):
    id: int
    broker: BrokerType
    account_name: Optional[str]
    account_id: Optional[str]
    is_active: bool
    initial_balance: float
    current_balance: float
    equity: Optional[float]
    margin_used: float
    peak_equity: Optional[float]
    current_drawdown_pct: float
    max_drawdown_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    session_trades_today: int
    session_date: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class EquitySnapshotRead(BaseModel):
    id: int
    account_id: int
    broker: Optional[str]
    equity: float
    balance: float
    drawdown_pct: float
    open_trades: int
    timestamp: datetime

    class Config:
        from_attributes = True
