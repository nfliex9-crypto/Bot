from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MarketType(StrEnum):
    FOREX = "forex"
    CRYPTO = "crypto"


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass(slots=True)
class InstrumentSpec:
    symbol: str
    market: MarketType
    quantity_step: float = 0.001
    min_quantity: float = 0.001
    tick_size: float = 0.0001
    contract_size: float = 1.0
    point_value: float = 1.0


@dataclass(slots=True)
class MarketSnapshot:
    symbol: str
    market: MarketType
    h1_bias: str
    m15_structure: str
    m5_context: dict[str, Any]
    atr: float
    timestamp: datetime


@dataclass(slots=True)
class TradeSignal:
    symbol: str
    market: MarketType
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit_levels: list[float]
    reason: str
    confidence: float = 0.0
    atr: float = 0.0
    pullback_level: float = 0.0
    bos_level: float = 0.0
    liquidity_level: float = 0.0
    h1_bias: str = "neutral"
    m15_trend: str = "neutral"
    session: str = ""
    features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class PositionPlan:
    symbol: str
    market: MarketType
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit_levels: list[float]
    quantity: float
    risk_amount: float
    confidence: float
    session: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NewsEvent:
    title: str
    currency: str
    impact: str
    starts_at: datetime
    source: str = "api"
