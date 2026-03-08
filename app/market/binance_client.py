from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from app.config import Settings

logger = logging.getLogger(__name__)


class BinanceMarketDataClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._try_connect()

    def _try_connect(self) -> None:
        try:
            from binance.client import Client  # type: ignore

            self._client = Client(self.settings.binance_api_key, self.settings.binance_api_secret, testnet=self.settings.binance_testnet)
        except Exception as exc:  # pragma: no cover - runtime fallback path
            logger.warning("Binance client unavailable: %s", exc)
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def get_ohlcv(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if self._client is None:
            return self._synthetic_ohlcv(timeframe, bars)

        interval = self._map_interval(timeframe)
        try:
            klines = self._client.get_klines(symbol=symbol, interval=interval, limit=bars)
            if not klines:
                return self._synthetic_ohlcv(timeframe, bars)

            df = pd.DataFrame(
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
            return pd.DataFrame(
                {
                    "time": pd.to_datetime(df["open_time"], unit="ms", utc=True),
                    "open": df["open"].astype(float),
                    "high": df["high"].astype(float),
                    "low": df["low"].astype(float),
                    "close": df["close"].astype(float),
                    "volume": df["volume"].astype(float),
                }
            )
        except Exception as exc:  # pragma: no cover - external API variability
            logger.error("Binance OHLCV fetch failed for %s: %s", symbol, exc)
            return self._synthetic_ohlcv(timeframe, bars)

    def _map_interval(self, timeframe: str) -> str:
        mapping = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h"}
        return mapping.get(timeframe, "5m")

    def _synthetic_ohlcv(self, timeframe: str, bars: int) -> pd.DataFrame:
        step = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60}.get(timeframe, 5)
        now = datetime.now(timezone.utc)
        idx = pd.date_range(end=now, periods=bars, freq=f"{step}min")
        close = pd.Series(25000 + (pd.Series(range(bars)).astype(float) * 0.5))
        open_ = close.shift(1).fillna(close.iloc[0])
        high = pd.concat([open_, close], axis=1).max(axis=1) + 2.0
        low = pd.concat([open_, close], axis=1).min(axis=1) - 2.0
        volume = pd.Series(50, index=range(bars), dtype=float)
        return pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": volume})

