from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from loguru import logger

from app.core.config import settings
from app.market_data.base import MarketDataProvider

TIMEFRAME_MAP: dict[str, int] = {}

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
except ImportError:
    mt5 = None  # type: ignore[assignment]
    logger.warning("MetaTrader5 package not available — MT5 provider will be disabled")


class MT5DataProvider(MarketDataProvider):
    """MetaTrader 5 data feed via the official Python package."""

    def __init__(self) -> None:
        self._connected = False

    async def connect(self) -> bool:
        if mt5 is None:
            logger.error("MetaTrader5 package not installed")
            return False

        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, self._init_mt5)
        self._connected = ok
        if ok:
            logger.info("MT5 connected successfully")
        else:
            logger.error("MT5 connection failed")
        return ok

    def _init_mt5(self) -> bool:
        if not mt5.initialize(path=settings.mt5_path or None):
            return False
        if settings.mt5_login:
            return mt5.login(
                login=int(settings.mt5_login),
                password=settings.mt5_password,
                server=settings.mt5_server,
            )
        return True

    async def disconnect(self) -> None:
        if mt5 is not None and self._connected:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mt5.shutdown)
            self._connected = False
            logger.info("MT5 disconnected")

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if mt5 is None or not self._connected:
            return pd.DataFrame()

        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            logger.error(f"Unsupported MT5 timeframe: {timeframe}")
            return pd.DataFrame()

        loop = asyncio.get_event_loop()

        if start:
            rates = await loop.run_in_executor(
                None, lambda: mt5.copy_rates_from(symbol, tf, start, count)
            )
        else:
            rates = await loop.run_in_executor(
                None, lambda: mt5.copy_rates_from_pos(symbol, tf, 0, count)
            )

        if rates is None or len(rates) == 0:
            logger.warning(f"No MT5 data for {symbol} {timeframe}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

    async def get_current_price(self, symbol: str) -> float:
        if mt5 is None or not self._connected:
            return 0.0

        loop = asyncio.get_event_loop()
        tick = await loop.run_in_executor(None, lambda: mt5.symbol_info_tick(symbol))
        if tick is None:
            return 0.0
        return (tick.bid + tick.ask) / 2.0

    async def get_symbol_info(self, symbol: str) -> dict | None:
        if mt5 is None or not self._connected:
            return None
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: mt5.symbol_info(symbol))
        if info is None:
            return None
        return {
            "symbol": symbol,
            "point": info.point,
            "digits": info.digits,
            "trade_contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
        }
