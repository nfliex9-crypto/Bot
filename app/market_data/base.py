from __future__ import annotations

import abc
from datetime import datetime
from typing import Optional

import pandas as pd


class MarketDataProvider(abc.ABC):
    """Abstract base for all market-data feeds."""

    @abc.abstractmethod
    async def connect(self) -> bool:
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        ...

    @abc.abstractmethod
    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Return OHLCV DataFrame with columns: timestamp, open, high, low, close, volume."""
        ...

    @abc.abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        ...
