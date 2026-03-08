"""Data models for trading signals and market structure."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


class MarketType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class TradeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class StrategyType(str, Enum):
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BREAK_OF_STRUCTURE = "break_of_structure"
    PULLBACK_ENTRY = "pullback_entry"


class StopType(str, Enum):
    ATR = "atr"
    STRUCTURE = "structure"


@dataclass
class SwingPoint:
    """Market structure swing high/low."""
    price: float
    time: datetime
    is_high: bool
    timeframe: str


@dataclass
class MarketStructure:
    """Break of structure / liquidity sweep context."""
    higher_highs: list[SwingPoint]
    higher_lows: list[SwingPoint]
    lower_highs: list[SwingPoint]
    lower_lows: list[SwingPoint]
    last_swing: SwingPoint
    bias: Literal["bullish", "bearish", "ranging"]
    timeframe: str


@dataclass
class TradeSignal:
    """Complete trade signal with all parameters."""
    symbol: str
    direction: TradeDirection
    strategy: StrategyType
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    stop_type: StopType
    atr_value: float
    risk_reward: float
    confidence: float  # 0-1 from AI
    market_type: MarketType
    timestamp: datetime
    market_structure: MarketStructure | None = None
    metadata: dict | None = None
