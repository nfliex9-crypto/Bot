from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import pandas as pd


@dataclass
class OHLCV:
    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TickData:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: datetime


@dataclass
class AccountInfo:
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    currency: str


class BaseConnector(ABC):
    """Abstract base class for market data and order connectors."""

    def __init__(self, name: str):
        self.name = name
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame: ...

    @abstractmethod
    async def get_tick(self, symbol: str) -> Optional[TickData]: ...

    @abstractmethod
    async def get_account_info(self) -> Optional[AccountInfo]: ...
