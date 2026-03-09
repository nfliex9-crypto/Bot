from __future__ import annotations

from abc import ABC, abstractmethod

import polars as pl


class MarketDataAdapter(ABC):
    @abstractmethod
    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pl.DataFrame:
        """Return OHLCV DataFrame with timestamp/open/high/low/close/volume."""
