from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.models import Candle
from data.feed import DataFeed

logger = logging.getLogger(__name__)


class CandleManager:
    """Manages multi-timeframe candle data with TA calculations."""

    def __init__(self, feed: DataFeed) -> None:
        self._feed = feed
        self._cache: Dict[str, pd.DataFrame] = {}

    def _cache_key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}_{timeframe}"

    async def refresh(self, symbol: str, timeframe: str, count: int = 200) -> pd.DataFrame:
        candles = await self._feed.get_candles(symbol, timeframe, count)
        if not candles:
            logger.warning("No candles for %s %s", symbol, timeframe)
            return pd.DataFrame()
        df = self._candles_to_df(candles)
        df = self._add_indicators(df)
        key = self._cache_key(symbol, timeframe)
        self._cache[key] = df
        return df

    def get_cached(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        return self._cache.get(self._cache_key(symbol, timeframe))

    @staticmethod
    def _candles_to_df(candles: List[Candle]) -> pd.DataFrame:
        data = [c.model_dump() for c in candles]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df

    @staticmethod
    def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df["atr"] = CandleManager._calc_atr(df, 14)
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["rsi"] = CandleManager._calc_rsi(df["close"], 14)

        df["higher_high"] = df["high"] > df["high"].shift(1)
        df["lower_low"] = df["low"] < df["low"].shift(1)
        df["body_size"] = abs(df["close"] - df["open"])
        df["upper_wick"] = df["high"] - df[["close", "open"]].max(axis=1)
        df["lower_wick"] = df[["close", "open"]].min(axis=1) - df["low"]
        df["range"] = df["high"] - df["low"]
        df["body_ratio"] = df["body_size"] / df["range"].replace(0, np.nan)
        df["volume_sma"] = df["volume"].rolling(20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"].replace(0, np.nan)

        return df

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
