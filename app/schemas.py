from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict


MarketType = Literal["forex", "crypto"]
Side = Literal["buy", "sell"]


@dataclass
class Signal:
    market: MarketType
    symbol: str
    side: Side
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr: float
    rr_to_tp1: float
    rule_score: float
    notes: str
    feature_payload: Dict[str, float]


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market: str
    symbol: str
    side: str
    mode: str
    quantity: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    status: str
    remaining_qty: float
    realized_pnl: float
    confidence: float
    hit_tp1: bool
    hit_tp2: bool
    hit_tp3: bool
    moved_to_breakeven: bool
    created_at: datetime

class StatusResponse(BaseModel):
    running: bool
    mode: str
    open_trades: int
    latest_equity: float
    latest_drawdown: float
    symbols: Dict[str, List[str]]


class TrainResponse(BaseModel):
    trained: bool
    samples: int
    accuracy: Optional[float]
    message: str

