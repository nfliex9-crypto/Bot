"""
Core data models used across the entire trading system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL_CLOSE = "partial_close"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class MarketBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StructureType(str, Enum):
    HIGHER_HIGH = "HH"
    HIGHER_LOW = "HL"
    LOWER_LOW = "LL"
    LOWER_HIGH = "LH"
    BREAK_OF_STRUCTURE = "BOS"
    CHANGE_OF_CHARACTER = "CHoCH"


@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = ""
    timeframe: str = ""


@dataclass
class SwingPoint:
    timestamp: datetime
    price: float
    is_high: bool
    strength: int = 1


@dataclass
class LiquidityZone:
    price_level: float
    zone_type: str  # "buy_side" or "sell_side"
    strength: int = 1
    swept: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    touch_count: int = 0


@dataclass
class StructureBreak:
    break_type: StructureType
    price: float
    timestamp: datetime
    direction: Direction
    confirmed: bool = False


@dataclass
class TradeSignal:
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    direction: Direction = Direction.LONG
    entry_price: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    confidence: float = 0.0
    strength: SignalStrength = SignalStrength.WEAK
    market_bias: MarketBias = MarketBias.NEUTRAL
    timeframe: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    ai_score: float = 0.0
    risk_reward: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class Trade:
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    signal: Optional[TradeSignal] = None
    symbol: str = ""
    direction: Direction = Direction.LONG
    entry_price: float = 0.0
    current_price: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    position_size: float = 0.0
    status: TradeStatus = TradeStatus.PENDING
    pnl: float = 0.0
    pnl_pct: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    broker_order_id: Optional[str] = None
    market: str = ""
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    breakeven_set: bool = False
    partial_closes: list = field(default_factory=list)

    @property
    def risk_amount(self) -> float:
        if self.direction == Direction.LONG:
            return abs(self.entry_price - self.stop_loss) * self.position_size
        return abs(self.stop_loss - self.entry_price) * self.position_size

    @property
    def is_profitable(self) -> bool:
        return self.pnl > 0


@dataclass
class AccountState:
    balance: float = 3000.0
    equity: float = 3000.0
    open_trades: int = 0
    daily_pnl: float = 0.0
    daily_trades: int = 0
    max_drawdown_reached: float = 0.0
    peak_balance: float = 3000.0
    session_trades: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def current_drawdown(self) -> float:
        if self.peak_balance == 0:
            return 0.0
        return (self.peak_balance - self.equity) / self.peak_balance

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
