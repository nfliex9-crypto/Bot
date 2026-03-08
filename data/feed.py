from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.enums import Market, Timeframe
from core.models import Candle
from config.settings import settings

logger = logging.getLogger(__name__)

TF_MAP_MT5: Dict[str, int] = {}
TF_MAP_BINANCE: Dict[str, str] = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "4h", "D1": "1d",
}


def _init_mt5_tf_map() -> None:
    """Lazy-load MT5 timeframe constants (MT5 may not be available on all systems)."""
    global TF_MAP_MT5
    if TF_MAP_MT5:
        return
    try:
        import MetaTrader5 as mt5
        TF_MAP_MT5.update({
            "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        })
    except ImportError:
        logger.warning("MetaTrader5 package not available — MT5 feed disabled")


class DataFeed(ABC):
    @abstractmethod
    async def get_candles(
        self, symbol: str, timeframe: str, count: int = 200
    ) -> List[Candle]:
        ...

    @abstractmethod
    async def get_current_price(self, symbol: str) -> float:
        ...


class MT5DataFeed(DataFeed):

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> bool:
        _init_mt5_tf_map()
        if not TF_MAP_MT5:
            return False
        try:
            import MetaTrader5 as mt5
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._mt5_init)
            self._initialized = result
            return result
        except Exception:
            logger.exception("Failed to initialize MT5")
            return False

    @staticmethod
    def _mt5_init() -> bool:
        import MetaTrader5 as mt5
        kwargs = {}
        if settings.mt5_path:
            kwargs["path"] = settings.mt5_path
        if settings.mt5_login:
            kwargs["login"] = settings.mt5_login
            kwargs["password"] = settings.mt5_password
            kwargs["server"] = settings.mt5_server
        return mt5.initialize(**kwargs)

    async def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> List[Candle]:
        if not self._initialized:
            return []
        import MetaTrader5 as mt5
        tf = TF_MAP_MT5.get(timeframe)
        if tf is None:
            return []
        loop = asyncio.get_event_loop()
        rates = await loop.run_in_executor(None, mt5.copy_rates_from_pos, symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return []
        candles = []
        for r in rates:
            candles.append(Candle(
                timestamp=datetime.utcfromtimestamp(r["time"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["tick_volume"]),
                symbol=symbol,
                timeframe=timeframe,
            ))
        return candles

    async def get_current_price(self, symbol: str) -> float:
        if not self._initialized:
            return 0.0
        import MetaTrader5 as mt5
        loop = asyncio.get_event_loop()
        tick = await loop.run_in_executor(None, mt5.symbol_info_tick, symbol)
        if tick is None:
            return 0.0
        return float((tick.bid + tick.ask) / 2)


class BinanceDataFeed(DataFeed):

    def __init__(self) -> None:
        self._client = None

    async def initialize(self) -> bool:
        try:
            from binance.client import Client
            if settings.binance_testnet:
                self._client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=True,
                )
            else:
                self._client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                )
            return True
        except Exception:
            logger.exception("Failed to initialize Binance client")
            return False

    async def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> List[Candle]:
        if self._client is None:
            return []
        interval = TF_MAP_BINANCE.get(timeframe, "5m")
        loop = asyncio.get_event_loop()
        try:
            klines = await loop.run_in_executor(
                None,
                lambda: self._client.get_klines(symbol=symbol, interval=interval, limit=count),
            )
        except Exception:
            logger.exception("Binance candle fetch failed for %s %s", symbol, timeframe)
            return []
        candles = []
        for k in klines:
            candles.append(Candle(
                timestamp=datetime.utcfromtimestamp(k[0] / 1000),
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
                symbol=symbol,
                timeframe=timeframe,
            ))
        return candles

    async def get_current_price(self, symbol: str) -> float:
        if self._client is None:
            return 0.0
        loop = asyncio.get_event_loop()
        try:
            ticker = await loop.run_in_executor(
                None,
                lambda: self._client.get_symbol_ticker(symbol=symbol),
            )
            return float(ticker["price"])
        except Exception:
            logger.exception("Binance price fetch failed for %s", symbol)
            return 0.0


class PaperDataFeed(DataFeed):
    """Wraps a real feed but prevents live order execution. Data is real."""

    def __init__(self, real_feed: DataFeed) -> None:
        self._feed = real_feed

    async def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> List[Candle]:
        return await self._feed.get_candles(symbol, timeframe, count)

    async def get_current_price(self, symbol: str) -> float:
        return await self._feed.get_current_price(symbol)
