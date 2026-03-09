from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import polars as pl

from .base import MarketDataAdapter


class SyntheticOHLCVAdapter(MarketDataAdapter):
    """Synthetic adapter for deterministic local testing."""

    def __init__(self, seed: int = 42) -> None:
        self.rng = np.random.default_rng(seed)

    def fetch_ohlcv(
        self,
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pl.DataFrame:
        if interval != "1d":
            raise ValueError("Synthetic adapter currently supports only 1d bars.")

        dates = pd.date_range(datetime.fromisoformat(start), datetime.fromisoformat(end), freq="B")
        n = len(dates)
        if n == 0:
            return pl.DataFrame()

        drift = 0.0002 + self.rng.normal(0, 0.00005)
        vol = 0.01 + abs(self.rng.normal(0, 0.002))
        rets = drift + vol * self.rng.normal(size=n)
        close = 100 * np.cumprod(1 + rets)
        open_ = np.roll(close, 1)
        open_[0] = close[0] * (1 + self.rng.normal(0, 0.001))
        high = np.maximum(open_, close) * (1 + np.abs(self.rng.normal(0, 0.003, n)))
        low = np.minimum(open_, close) * (1 - np.abs(self.rng.normal(0, 0.003, n)))
        volume = np.exp(self.rng.normal(13, 0.4, n))

        pdf = pd.DataFrame(
            {
                "timestamp": dates,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
        return pl.from_pandas(pdf)
