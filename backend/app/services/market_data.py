from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from app.core.config import Settings

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mt5 = None

try:
    from binance.client import Client
except Exception:  # pragma: no cover - optional dependency
    Client = None


class MarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._binance_client = None
        if Client and settings.binance_api_key and settings.binance_api_secret:
            self._binance_client = Client(settings.binance_api_key, settings.binance_api_secret)

    def get_ohlcv(self, market: str, symbol: str, timeframe: str = "M15", bars: int = 300) -> pd.DataFrame:
        market_normalized = market.lower()
        if market_normalized == "forex":
            frame = self._from_mt5(symbol=symbol, timeframe=timeframe, bars=bars)
            if frame is not None and not frame.empty:
                return frame
        elif market_normalized == "crypto":
            frame = self._from_binance(symbol=symbol, timeframe=timeframe, bars=bars)
            if frame is not None and not frame.empty:
                return frame

        # Safe fallback for development/testing when broker APIs are unavailable.
        return self._synthetic_ohlcv(bars=bars)

    def _from_mt5(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame | None:
        if mt5 is None:
            return None
        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
        }
        if not mt5.initialize():
            return None
        rates = mt5.copy_rates_from_pos(symbol, timeframe_map.get(timeframe, mt5.TIMEFRAME_M15), 0, bars)
        mt5.shutdown()
        if rates is None:
            return None
        frame = pd.DataFrame(rates)
        if frame.empty:
            return None
        frame = frame.rename(columns={"tick_volume": "volume"})
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        return frame[["time", "open", "high", "low", "close", "volume"]].astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float}
        )

    def _from_binance(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame | None:
        if self._binance_client is None:
            return None
        interval_map = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "1h"}
        interval = interval_map.get(timeframe, "15m")
        klines = self._binance_client.get_klines(symbol=symbol, interval=interval, limit=bars)
        if not klines:
            return None
        frame = pd.DataFrame(
            klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )
        frame["time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        return frame[["time", "open", "high", "low", "close", "volume"]].astype(
            {"open": float, "high": float, "low": float, "close": float, "volume": float}
        )

    def _synthetic_ohlcv(self, bars: int) -> pd.DataFrame:
        rng = np.random.default_rng(7)
        returns = rng.normal(0, 0.0018, size=bars)
        close = 1.10 * np.exp(np.cumsum(returns))
        high = close + np.abs(rng.normal(0, 0.0009, size=bars))
        low = close - np.abs(rng.normal(0, 0.0009, size=bars))
        open_ = close + rng.normal(0, 0.0004, size=bars)
        volume = rng.integers(100, 1000, size=bars)
        start = datetime.now(UTC) - timedelta(minutes=15 * bars)
        time = [start + timedelta(minutes=15 * i) for i in range(bars)]
        return pd.DataFrame(
            {
                "time": time,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        ).astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
