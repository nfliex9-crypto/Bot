from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import ccxt
import pandas as pd

from app.core.config import Settings
from app.domain.models import MarketType

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - optional runtime dependency
    mt5 = None


def _ohlcv_to_frame(rows: list[list[float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = frame[column].astype(float)
    return frame


class MarketDataProvider(Protocol):
    async def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        ...

    async def fetch_last_price(self, symbol: str) -> float:
        ...


class BinanceMarketDataProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.exchange = ccxt.binance(
            {
                "apiKey": settings.binance_api_key,
                "secret": settings.binance_api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            }
        )
        if settings.binance_testnet:
            self.exchange.set_sandbox_mode(True)

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        rows = await asyncio.to_thread(self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        return _ohlcv_to_frame(rows)

    async def fetch_last_price(self, symbol: str) -> float:
        ticker = await asyncio.to_thread(self.exchange.fetch_ticker, symbol)
        return float(ticker["last"])


class MT5MarketDataProvider:
    _timeframe_map = {
        "H1": 16385,
        "M15": 15,
        "M5": 5,
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        initialized = mt5.initialize(
            path=settings.mt5_path,
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        )
        if not initialized:
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")

    async def fetch_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        mapped = getattr(mt5, f"TIMEFRAME_{timeframe}", None) or self._timeframe_map.get(timeframe)
        if mapped is None:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
        rows = await asyncio.to_thread(mt5.copy_rates_from_pos, symbol, mapped, 0, limit)
        frame = pd.DataFrame(rows)
        frame["timestamp"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        return frame.rename(columns={"tick_volume": "volume"})[
            ["timestamp", "open", "high", "low", "close", "volume"]
        ]

    async def fetch_last_price(self, symbol: str) -> float:
        tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
        if tick is None:
            raise RuntimeError(f"Could not fetch MT5 tick for {symbol}")
        return float(tick.ask or tick.bid)


@dataclass(slots=True)
class CompositeMarketDataService:
    forex: MarketDataProvider
    crypto: MarketDataProvider

    async def fetch_candles(self, market: MarketType, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        provider = self.forex if market == MarketType.FOREX else self.crypto
        return await provider.fetch_candles(symbol, timeframe, limit)

    async def fetch_last_price(self, market: MarketType, symbol: str) -> float:
        provider = self.forex if market == MarketType.FOREX else self.crypto
        return await provider.fetch_last_price(symbol)
