from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.market.binance_client import BinanceMarketClient
from app.market.mt5_client import MT5Client


class MarketDataProvider:
    def __init__(self, mt5_client: MT5Client, binance_client: BinanceMarketClient):
        self.mt5_client = mt5_client
        self.binance_client = binance_client

    def _synthetic_data(self, limit: int = 200) -> pd.DataFrame:
        now = datetime.utcnow()
        times = [now - timedelta(minutes=5 * i) for i in range(limit)][::-1]
        base = 100 + np.cumsum(np.random.normal(0, 0.2, size=limit))
        high = base + np.abs(np.random.normal(0.1, 0.05, size=limit))
        low = base - np.abs(np.random.normal(0.1, 0.05, size=limit))
        open_ = np.roll(base, 1)
        open_[0] = base[0]
        volume = np.random.randint(100, 1000, size=limit)
        return pd.DataFrame(
            {
                "time": times,
                "open": open_,
                "high": high,
                "low": low,
                "close": base,
                "volume": volume,
            }
        )

    def get_forex_candles(self, symbol: str, limit: int = 200) -> pd.DataFrame:
        data = self.mt5_client.get_rates(symbol=symbol, timeframe=5, limit=limit)
        return data if not data.empty else self._synthetic_data(limit)

    def get_crypto_candles(self, symbol: str, limit: int = 200) -> pd.DataFrame:
        data = self.binance_client.get_klines(symbol=symbol, interval="5m", limit=limit)
        return data if not data.empty else self._synthetic_data(limit)
