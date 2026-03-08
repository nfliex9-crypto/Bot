from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import pandas as pd


class Market(StrEnum):
    FOREX = "forex"
    CRYPTO = "crypto"


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class TradeStatus(StrEnum):
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"
    REJECTED = "rejected"


class StopMethod(StrEnum):
    ATR = "atr"
    STRUCTURE = "structure"


@dataclass(slots=True)
class MarketSnapshot:
    market: Market
    symbol: str
    h1: pd.DataFrame
    m15: pd.DataFrame
    m5: pd.DataFrame
    current_price: float
    timestamp: datetime


@dataclass(slots=True)
class TradeSetup:
    market: Market
    symbol: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_per_unit: float
    strategy_score: float
    rationale: list[str]
    session_label: str
    structure_level: float
    atr_value: float
    metadata: dict[str, float | str | bool] = field(default_factory=dict)
    ai_confidence: float = 0.0
    confidence: float = 0.0


@dataclass(slots=True)
class FilterResult:
    passed: bool
    session_label: str
    blocked_reason: str | None = None
    extra: dict[str, str | float | bool] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionResult:
    accepted: bool
    provider_order_id: str
    executed_price: float
    executed_quantity: float
    mode: TradingMode
    venue: str
    details: dict[str, str | float | bool] = field(default_factory=dict)
