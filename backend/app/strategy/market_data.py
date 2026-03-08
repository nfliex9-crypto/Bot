from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.core.config import get_settings

settings = get_settings()

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional runtime dependency
    mt5 = None

try:
    from binance.client import Client as BinanceClient
except Exception:  # pragma: no cover - optional runtime dependency
    BinanceClient = None


MT5_TIMEFRAME_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
}

BINANCE_INTERVAL_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
}


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    return df[["time", "open", "high", "low", "close", "volume"]].astype(
        {
            "open": "float64",
            "high": "float64",
            "low": "float64",
            "close": "float64",
            "volume": "float64",
        }
    )


class ForexDataProvider:
    def get_bars(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        if mt5 is None:
            return self._synthetic(symbol, bars)

        if not mt5.initialize():
            return self._synthetic(symbol, bars)

        rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, f"TIMEFRAME_{timeframe}", mt5.TIMEFRAME_M15), 0, bars)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            return self._synthetic(symbol, bars)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "volume"})
        return _normalize_ohlcv(df)

    @staticmethod
    def _synthetic(symbol: str, bars: int) -> pd.DataFrame:
        idx = pd.date_range(end=datetime.utcnow(), periods=bars, freq="15min")
        seed = abs(hash(symbol)) % 100
        base = pd.Series(range(bars), dtype="float64") * 0.0001 + 1.0 + seed / 10000
        close = base + (pd.Series(range(bars)) % 5 - 2) * 0.00005
        df = pd.DataFrame(
            {
                "time": idx,
                "open": close.shift(1).fillna(close.iloc[0]),
                "high": close + 0.0002,
                "low": close - 0.0002,
                "close": close,
                "volume": 1000.0,
            }
        )
        return _normalize_ohlcv(df)


class CryptoDataProvider:
    def __init__(self) -> None:
        self.client: Any | None = None
        if BinanceClient and settings.binance_api_key and settings.binance_api_secret:
            self.client = BinanceClient(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_api_secret,
                testnet=settings.binance_testnet,
            )

    def get_bars(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        if not self.client:
            return self._synthetic(symbol, bars)

        klines = self.client.get_klines(
            symbol=symbol,
            interval=BINANCE_INTERVAL_MAP.get(timeframe, "15m"),
            limit=bars,
        )
        if not klines:
            return self._synthetic(symbol, bars)

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
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )
        df["time"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df[["time", "open", "high", "low", "close", "volume"]]
        return _normalize_ohlcv(df)

    @staticmethod
    def _synthetic(symbol: str, bars: int) -> pd.DataFrame:
        idx = pd.date_range(end=datetime.utcnow(), periods=bars, freq="15min")
        seed = abs(hash(symbol)) % 1000
        base = pd.Series(range(bars), dtype="float64") * 0.5 + 40000 + seed
        close = base + (pd.Series(range(bars)) % 7 - 3) * 2.0
        df = pd.DataFrame(
            {
                "time": idx,
                "open": close.shift(1).fillna(close.iloc[0]),
                "high": close + 6.0,
                "low": close - 6.0,
                "close": close,
                "volume": 25.0,
            }
        )
        return _normalize_ohlcv(df)
