from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Dict

import numpy as np
import pandas as pd
import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover
    mt5 = None  # type: ignore[assignment]


TIMEFRAME_LOOKUP = {"H1": 60, "M15": 15, "M5": 5}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    required = ["time", "open", "high", "low", "close", "volume"]
    frame = df.copy()
    frame = frame[required]
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame.sort_values("time", inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


class BinanceKlineProvider:
    base_url = "https://api.binance.com/api/v3/klines"

    def fetch(self, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        params = {"symbol": symbol, "interval": interval.lower(), "limit": limit}
        response = httpx.get(self.base_url, params=params, timeout=10.0)
        response.raise_for_status()
        rows = response.json()
        if not rows:
            raise ValueError("No Binance klines returned.")
        frame = pd.DataFrame(rows)
        frame = frame.rename(
            columns={
                0: "open_time",
                1: "open",
                2: "high",
                3: "low",
                4: "close",
                5: "volume",
            }
        )
        frame["time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        for col in ("open", "high", "low", "close", "volume"):
            frame[col] = frame[col].astype(float)
        return _normalize(frame[["time", "open", "high", "low", "close", "volume"]])


class MT5RateProvider:
    tf_map = {"H1": mt5.TIMEFRAME_H1 if mt5 else None, "M15": mt5.TIMEFRAME_M15 if mt5 else None, "M5": mt5.TIMEFRAME_M5 if mt5 else None}

    def fetch(self, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package unavailable.")
        timeframe = self.tf_map.get(interval)
        if timeframe is None:
            raise ValueError(f"Unsupported MT5 interval: {interval}")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, limit)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"No MT5 rates for {symbol}/{interval}")
        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.rename(columns={"tick_volume": "volume"})
        return _normalize(frame[["time", "open", "high", "low", "close", "volume"]])


class SyntheticProvider:
    def fetch(self, symbol: str, interval: str, limit: int = 300) -> pd.DataFrame:
        minutes = TIMEFRAME_LOOKUP[interval]
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        times = [now - timedelta(minutes=minutes * (limit - i)) for i in range(limit)]
        seed = sum(ord(c) for c in symbol + interval)
        rng = np.random.default_rng(seed)

        base = 1.0 + (seed % 1000) / 1000
        drift = np.linspace(0, 0.01, num=limit)
        noise = rng.normal(0, 0.001, size=limit)
        close = base + drift + np.cumsum(noise)
        open_ = np.concatenate([[close[0]], close[:-1]])
        high = np.maximum(open_, close) + np.abs(rng.normal(0.0005, 0.0002, size=limit))
        low = np.minimum(open_, close) - np.abs(rng.normal(0.0005, 0.0002, size=limit))
        volume = rng.integers(100, 500, size=limit)

        frame = pd.DataFrame(
            {"time": times, "open": open_, "high": high, "low": low, "close": close, "volume": volume}
        )
        return _normalize(frame)


class MultiMarketDataService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.binance = BinanceKlineProvider()
        self.mt5 = MT5RateProvider()
        self.synthetic = SyntheticProvider()

    def fetch_mtf(self, market: str, symbol: str, limit: int = 300) -> Dict[str, pd.DataFrame]:
        intervals = ["H1", "M15", "M5"]
        data: Dict[str, pd.DataFrame] = {}

        for interval in intervals:
            try:
                if market == "crypto":
                    data[interval] = self.binance.fetch(symbol, interval, limit=limit)
                else:
                    data[interval] = self.mt5.fetch(symbol, interval, limit=limit)
            except Exception as exc:
                if self.settings.trading_mode == "paper":
                    logger.warning("Falling back to synthetic feed for %s %s/%s: %s", market, symbol, interval, exc)
                    data[interval] = self.synthetic.fetch(symbol, interval, limit=limit)
                else:
                    raise

        return data

