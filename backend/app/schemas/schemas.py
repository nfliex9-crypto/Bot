from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignalResponse(BaseModel):
    symbol: str
    market_type: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    risk_reward: float
    strategy: str
    timestamp: str
    details: Optional[dict] = None


class TradeResponse(BaseModel):
    id: UUID
    symbol: str
    market_type: str
    side: str
    status: str
    entry_price: float
    stop_loss: float
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    lot_size: float
    ai_confidence: Optional[float]
    pnl: Optional[float]
    pnl_percent: Optional[float]
    opened_at: datetime
    closed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ExecuteSignalRequest(BaseModel):
    symbol: str
    market_type: str = "forex"
    timeframe: str = "H1"
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    risk_reward: float
    strategy: str


class ExecutionResponse(BaseModel):
    executed: bool
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    entry_price: Optional[float] = None
    lot_size: Optional[float] = None
    confidence: Optional[float] = None
    risk_amount: Optional[float] = None
    reason: Optional[str] = None


class DashboardResponse(BaseModel):
    equity: dict
    risk_status: dict
    active_trades: list
    ai_model: dict
    connections: dict


class RiskStatusResponse(BaseModel):
    active_trades: int
    session_trades: int
    max_trades_per_session: int
    current_drawdown: float
    max_drawdown: float
    peak_equity: float
    current_equity: float
    risk_per_trade: float
    can_trade: bool


class AIModelMetricsResponse(BaseModel):
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    model_version: str = ""
    top_features: Optional[dict] = None


class EquitySnapshotResponse(BaseModel):
    balance: float
    equity: float
    drawdown: float
    drawdown_percent: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class TrainModelRequest(BaseModel):
    symbol: str = "EURUSD"
    timeframe: str = "H1"


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    connections: dict
