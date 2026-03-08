"""
Base broker interface.

All broker implementations must implement this interface.
This ensures the trading bot can work with any broker
by switching the broker connector.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import pandas as pd


@dataclass
class TickData:
    symbol: str
    bid: float
    ask: float
    last: float
    spread: float
    timestamp: Any = None


@dataclass
class OHLCV:
    symbol: str
    timeframe: str
    data: pd.DataFrame  # columns: open, high, low, close, volume, time


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    ticket: Optional[str] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    lot_size: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    error: Optional[str] = None
    raw: Optional[Dict] = None


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str = "USD"
    leverage: int = 100
    profit: float = 0.0


class BaseBroker(ABC):
    """Abstract base class for all broker connectors."""

    def __init__(self, paper_mode: bool = True):
        self.paper_mode = paper_mode
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the broker."""
        ...

    @abstractmethod
    async def disconnect(self):
        """Close the broker connection."""
        ...

    @abstractmethod
    async def get_account_info(self) -> AccountInfo:
        """Get current account information."""
        ...

    @abstractmethod
    async def get_tick(self, symbol: str) -> Optional[TickData]:
        """Get current bid/ask prices."""
        ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
    ) -> Optional[OHLCV]:
        """Fetch OHLCV candles."""
        ...

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        direction: str,     # "long" | "short"
        lot_size: float,
        stop_loss: float,
        take_profit: float,
        comment: str = "",
    ) -> OrderResult:
        """Place a market order."""
        ...

    @abstractmethod
    async def close_order(
        self,
        ticket: str,
        lot_size: Optional[float] = None,
    ) -> OrderResult:
        """Close an open order (full or partial)."""
        ...

    @abstractmethod
    async def modify_order(
        self,
        ticket: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> OrderResult:
        """Modify an open order's SL/TP."""
        ...

    @abstractmethod
    async def get_open_orders(self) -> List[Dict]:
        """Get all currently open orders."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _normalize_timeframe(self, tf: str) -> Any:
        """Override in subclass to convert timeframe string to broker-specific format."""
        return tf
