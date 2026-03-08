"""
MetaTrader 5 market data provider for Forex pairs.
Handles connection management, candle retrieval, and tick data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import MT5Config
from core.logger import get_logger
from core.models import OHLCV

logger = get_logger("data.mt5")

TIMEFRAME_MAP = {}

try:
    import MetaTrader5 as mt5

    TIMEFRAME_MAP = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 not available — MT5 provider will run in stub mode")


class MT5DataProvider:
    def __init__(self, config: MT5Config):
        self.config = config
        self._connected = False

    async def connect(self) -> bool:
        if not MT5_AVAILABLE:
            logger.warning("MT5 library not installed, running in stub mode")
            return False

        try:
            init_kwargs = {"login": self.config.login, "password": self.config.password,
                           "server": self.config.server, "timeout": self.config.timeout}
            if self.config.path:
                init_kwargs["path"] = self.config.path

            success = await asyncio.to_thread(mt5.initialize, **init_kwargs)
            if not success:
                error = mt5.last_error()
                logger.error(f"MT5 init failed: {error}")
                return False

            self._connected = True
            info = mt5.account_info()
            if info:
                logger.info(f"MT5 connected — Account #{info.login}, Balance: {info.balance}")
            return True
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    async def disconnect(self):
        if MT5_AVAILABLE and self._connected:
            await asyncio.to_thread(mt5.shutdown)
            self._connected = False
            logger.info("MT5 disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def get_candles(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> pd.DataFrame:
        if not self._connected:
            return self._empty_df()

        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            logger.error(f"Unknown timeframe: {timeframe}")
            return self._empty_df()

        try:
            rates = await asyncio.to_thread(mt5.copy_rates_from_pos, symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                logger.warning(f"No data for {symbol} {timeframe}")
                return self._empty_df()

            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            df.rename(columns={
                "time": "timestamp", "open": "open", "high": "high",
                "low": "low", "close": "close", "tick_volume": "volume",
            }, inplace=True)
            df["symbol"] = symbol
            df["timeframe"] = timeframe
            return df[["timestamp", "open", "high", "low", "close", "volume", "symbol", "timeframe"]]
        except Exception as e:
            logger.error(f"Error fetching MT5 candles for {symbol}: {e}")
            return self._empty_df()

    async def get_current_price(self, symbol: str) -> Optional[dict]:
        if not self._connected:
            return None
        try:
            tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
            if tick is None:
                return None
            return {"bid": tick.bid, "ask": tick.ask, "last": tick.last, "time": datetime.utcnow()}
        except Exception as e:
            logger.error(f"Error getting tick for {symbol}: {e}")
            return None

    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        if not self._connected:
            return None
        try:
            info = await asyncio.to_thread(mt5.symbol_info, symbol)
            if info is None:
                return None
            return {
                "symbol": info.name,
                "digits": info.digits,
                "point": info.point,
                "trade_contract_size": info.trade_contract_size,
                "volume_min": info.volume_min,
                "volume_max": info.volume_max,
                "volume_step": info.volume_step,
            }
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None

    def _empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume", "symbol", "timeframe"]
        )
