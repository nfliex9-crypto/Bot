from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

import pandas as pd


# ─── Enumerations ─────────────────────────────────────────────────────────────

class Market(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class MarketBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TrendStructure(str, Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGING = "ranging"


class Session(str, Enum):
    LONDON = "london"
    NEW_YORK = "new_york"
    LONDON_NY_OVERLAP = "london_ny_overlap"
    ASIAN = "asian"
    OFF = "off"


class SignalType(str, Enum):
    LIQUIDITY_SWEEP_LONG = "liquidity_sweep_long"
    LIQUIDITY_SWEEP_SHORT = "liquidity_sweep_short"
    BOS_LONG = "bos_long"
    BOS_SHORT = "bos_short"
    PULLBACK_LONG = "pullback_long"
    PULLBACK_SHORT = "pullback_short"


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class OHLCV:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str
    timeframe: str


@dataclass
class SwingPoint:
    price: float
    index: int
    timestamp: datetime
    is_high: bool


@dataclass
class LiquiditySweepSignal:
    symbol: str
    direction: Direction
    sweep_price: float
    liquidity_level: float
    reversal_candle_close: float
    timestamp: datetime
    confirmed: bool = False
    strength: float = 0.0


@dataclass
class BOSSignal:
    symbol: str
    direction: Direction
    break_price: float
    previous_swing: float
    timestamp: datetime
    confirmed: bool = False
    bars_confirmed: int = 0


@dataclass
class PullbackSignal:
    symbol: str
    direction: Direction
    entry_price: float
    fib_level: str
    swing_low: float
    swing_high: float
    timestamp: datetime
    valid: bool = False
    order_block_price: Optional[float] = None


@dataclass
class MultiTimeframeAnalysis:
    symbol: str
    timestamp: datetime
    h1_bias: MarketBias = MarketBias.NEUTRAL
    m15_structure: TrendStructure = TrendStructure.RANGING
    m5_entry_signal: Optional[str] = None
    sweep_signal: Optional[LiquiditySweepSignal] = None
    bos_signal: Optional[BOSSignal] = None
    pullback_signal: Optional[PullbackSignal] = None
    aligned: bool = False

    def is_bullish_aligned(self) -> bool:
        return (
            self.h1_bias == MarketBias.BULLISH
            and self.m15_structure == TrendStructure.UPTREND
            and self.sweep_signal is not None
            and self.sweep_signal.direction == Direction.LONG
            and self.bos_signal is not None
            and self.bos_signal.direction == Direction.LONG
        )

    def is_bearish_aligned(self) -> bool:
        return (
            self.h1_bias == MarketBias.BEARISH
            and self.m15_structure == TrendStructure.DOWNTREND
            and self.sweep_signal is not None
            and self.sweep_signal.direction == Direction.SHORT
            and self.bos_signal is not None
            and self.bos_signal.direction == Direction.SHORT
        )


@dataclass
class TradeSignal:
    symbol: str
    market: Market
    direction: Direction
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_amount: float
    risk_reward: float
    atr_value: float
    ai_confidence: float
    session: Session
    mtf_analysis: MultiTimeframeAnalysis
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_id: str = ""
    signal_type: str = ""
    strategy_signals: Dict = field(default_factory=dict)


@dataclass
class OpenTrade:
    trade_id: str
    symbol: str
    market: Market
    direction: Direction
    entry_price: float
    current_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_amount: float
    opened_at: datetime
    status: TradeStatus = TradeStatus.OPEN
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    breakeven_moved: bool = False
    unrealised_pnl: float = 0.0
    broker_order_id: Optional[str] = None

    def update_pnl(self, current_price: float, pip_value: float = 10.0) -> None:
        self.current_price = current_price
        if self.direction == Direction.LONG:
            diff = current_price - self.entry_price
        else:
            diff = self.entry_price - current_price
        self.unrealised_pnl = diff * self.lot_size * pip_value


@dataclass
class AccountState:
    balance: float
    equity: float
    open_pnl: float = 0.0
    daily_pnl: float = 0.0
    session_trades: int = 0
    peak_equity: float = 0.0
    drawdown_pct: float = 0.0
    open_trades: List[OpenTrade] = field(default_factory=list)

    def update_drawdown(self) -> None:
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
        if self.peak_equity > 0:
            self.drawdown_pct = (self.peak_equity - self.equity) / self.peak_equity

    @property
    def max_drawdown_breached(self) -> bool:
        from config.settings import settings
        return self.drawdown_pct >= settings.max_drawdown

    @property
    def session_limit_reached(self) -> bool:
        from config.settings import settings
        return self.session_trades >= settings.max_trades_per_session
