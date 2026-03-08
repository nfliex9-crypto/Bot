from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class MarketType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass(slots=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(slots=True)
class SymbolSpec:
    symbol: str
    market: MarketType
    base_currency: str
    quote_currency: str
    tick_size: float
    tick_value: float
    min_qty: float
    qty_step: float
    max_qty: float | None = None
    price_precision: int = 5
    qty_precision: int = 4


@dataclass(slots=True)
class SignalFeatures:
    values: dict[str, float]


@dataclass(slots=True)
class SignalContext:
    bias: TradeSide | None
    sweep_detected: bool
    bos_level: float | None
    pullback_level: float | None
    atr: float
    structure_stop: float | None
    feature_map: dict[str, float]
    rationale: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TradeSignal:
    symbol: str
    market: MarketType
    side: TradeSide
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    stop_method: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop_loss)


@dataclass(slots=True)
class SizedTradeSignal(TradeSignal):
    position_size: float = 0.0
    risk_amount: float = 0.0


@dataclass(slots=True)
class AccountSnapshot:
    balance: float
    equity: float
    peak_balance: float
    session_trade_count: int
    open_positions: int = 0


@dataclass(slots=True)
class OpenTrade:
    trade_id: str
    symbol: str
    market: MarketType
    side: TradeSide
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    position_size: float
    remaining_size: float
    confidence: float
    mode: TradingMode
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    break_even_moved: bool = False
    broker_trade_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EconomicEvent:
    title: str
    currency: str
    impact: str
    starts_at: datetime
    source: str = "api"


def default_symbol_specs() -> dict[str, SymbolSpec]:
    return {
        "EURUSD": SymbolSpec(
            symbol="EURUSD",
            market=MarketType.FOREX,
            base_currency="EUR",
            quote_currency="USD",
            tick_size=0.00001,
            tick_value=1.0,
            min_qty=0.01,
            qty_step=0.01,
            max_qty=50.0,
            price_precision=5,
            qty_precision=2,
        ),
        "GBPUSD": SymbolSpec(
            symbol="GBPUSD",
            market=MarketType.FOREX,
            base_currency="GBP",
            quote_currency="USD",
            tick_size=0.00001,
            tick_value=1.0,
            min_qty=0.01,
            qty_step=0.01,
            max_qty=50.0,
            price_precision=5,
            qty_precision=2,
        ),
        "BTC/USDT": SymbolSpec(
            symbol="BTC/USDT",
            market=MarketType.CRYPTO,
            base_currency="BTC",
            quote_currency="USDT",
            tick_size=0.1,
            tick_value=0.1,
            min_qty=0.001,
            qty_step=0.001,
            max_qty=10.0,
            price_precision=1,
            qty_precision=3,
        ),
        "ETH/USDT": SymbolSpec(
            symbol="ETH/USDT",
            market=MarketType.CRYPTO,
            base_currency="ETH",
            quote_currency="USDT",
            tick_size=0.01,
            tick_value=0.01,
            min_qty=0.01,
            qty_step=0.01,
            max_qty=100.0,
            price_precision=2,
            qty_precision=2,
        ),
    }
