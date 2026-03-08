from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from core.enums import Bias, Direction, Market, SignalType, TradeStatus


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = ""
    timeframe: str = ""


class SwingPoint(BaseModel):
    timestamp: datetime
    price: float
    is_high: bool
    index: int


class StructureBreak(BaseModel):
    timestamp: datetime
    price: float
    direction: Direction
    broken_level: float
    timeframe: str


class LiquidityZone(BaseModel):
    price_level: float
    zone_high: float
    zone_low: float
    touches: int = 0
    swept: bool = False
    timestamp: datetime
    timeframe: str


class MarketContext(BaseModel):
    symbol: str
    market: Market
    h1_bias: Bias = Bias.NEUTRAL
    m15_structure: Optional[StructureBreak] = None
    m5_entry_valid: bool = False
    atr_h1: float = 0.0
    atr_m15: float = 0.0
    atr_m5: float = 0.0
    current_price: float = 0.0
    liquidity_zones: List[LiquidityZone] = Field(default_factory=list)
    swing_highs: List[SwingPoint] = Field(default_factory=list)
    swing_lows: List[SwingPoint] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TradeSignal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    market: Market
    direction: Direction
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    risk_reward: float
    confidence: float = 0.0
    context: Optional[MarketContext] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    features: Dict[str, float] = Field(default_factory=dict)


class TradeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str
    symbol: str
    market: Market
    direction: Direction
    status: TradeStatus = TradeStatus.PENDING
    entry_price: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    breakeven_set: bool = False
    position_size: float = 0.0
    risk_amount: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    confidence: float = 0.0
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    close_reason: str = ""
    broker_order_id: str = ""
    metadata: Dict[str, str] = Field(default_factory=dict)


class AccountState(BaseModel):
    balance: float = 3000.0
    equity: float = 3000.0
    initial_balance: float = 3000.0
    open_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown_pct: float = 0.0
    peak_balance: float = 3000.0
    session_trades: int = 0
    daily_pnl: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def win_rate(self) -> float:
        total = self.winning_trades + self.losing_trades
        return (self.winning_trades / total * 100) if total > 0 else 0.0


class NewsEvent(BaseModel):
    title: str
    currency: str
    impact: str
    datetime_utc: datetime
    forecast: str = ""
    previous: str = ""
