"""
MetaTrader5 market data connector.
Wraps the MT5 Python API in an async-compatible interface.
MT5 itself is synchronous, so we run blocking calls in a thread pool.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger
from functools import partial

from src.connectors.base import BaseConnector, TickData, AccountInfo
from config.settings import settings

# MT5 is Windows-only; graceful import fallback for Linux CI/CD
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available on this platform")

MT5_TIMEFRAME_MAP = {
    "M1": 1,    # mt5.TIMEFRAME_M1
    "M5": 5,    # mt5.TIMEFRAME_M5
    "M15": 15,  # mt5.TIMEFRAME_M15
    "M30": 30,  # mt5.TIMEFRAME_M30
    "H1": 16385,  # mt5.TIMEFRAME_H1
    "H4": 16388,  # mt5.TIMEFRAME_H4
    "D1": 16408,  # mt5.TIMEFRAME_D1
}


class MT5Connector(BaseConnector):
    """Async-compatible connector for MetaTrader5."""

    def __init__(self):
        super().__init__("MT5")
        self._loop = None
        self._executor = None

    async def connect(self) -> bool:
        if not MT5_AVAILABLE:
            logger.warning("MT5 not available – running in simulation mode")
            self._connected = True
            return True

        def _init():
            if settings.mt5_path:
                return mt5.initialize(
                    path=settings.mt5_path,
                    login=settings.mt5_login,
                    password=settings.mt5_password,
                    server=settings.mt5_server,
                    timeout=10000,
                )
            return mt5.initialize(
                login=settings.mt5_login,
                password=settings.mt5_password,
                server=settings.mt5_server,
                timeout=10000,
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _init)
        if result:
            info = await loop.run_in_executor(None, mt5.terminal_info)
            logger.info(f"MT5 connected | build={info.build} community_connection={info.community_connection}")
            self._connected = True
        else:
            err = mt5.last_error() if mt5 else "N/A"
            logger.error(f"MT5 init failed: {err}")
        return self._connected

    async def disconnect(self) -> None:
        if MT5_AVAILABLE and self._connected:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mt5.shutdown)
        self._connected = False
        logger.info("MT5 disconnected")

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if not MT5_AVAILABLE:
            return self._generate_sim_ohlcv(symbol, timeframe, count)

        tf_const = MT5_TIMEFRAME_MAP.get(timeframe, MT5_TIMEFRAME_MAP["H1"])

        def _fetch():
            if start:
                rates = mt5.copy_rates_from(symbol, tf_const, start, count)
            else:
                rates = mt5.copy_rates_from_pos(symbol, tf_const, 0, count)
            return rates

        loop = asyncio.get_event_loop()
        rates = await loop.run_in_executor(None, _fetch)

        if rates is None or len(rates) == 0:
            logger.warning(f"No OHLCV data for {symbol} {timeframe}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(columns={
            "time": "open_time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "volume",
        })
        df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
        df = df.sort_values("open_time").reset_index(drop=True)
        return df

    async def get_tick(self, symbol: str) -> Optional[TickData]:
        if not MT5_AVAILABLE:
            return self._simulate_tick(symbol)

        def _fetch():
            return mt5.symbol_info_tick(symbol)

        loop = asyncio.get_event_loop()
        tick = await loop.run_in_executor(None, _fetch)

        if tick is None:
            return None

        return TickData(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            last=tick.last,
            timestamp=datetime.fromtimestamp(tick.time, tz=timezone.utc),
        )

    async def get_account_info(self) -> Optional[AccountInfo]:
        if not MT5_AVAILABLE:
            return AccountInfo(
                balance=settings.account_balance,
                equity=settings.account_balance,
                margin=0.0,
                free_margin=settings.account_balance,
                margin_level=0.0,
                currency="USD",
            )

        def _fetch():
            return mt5.account_info()

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _fetch)

        if info is None:
            return None

        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin=info.margin,
            free_margin=info.margin_free,
            margin_level=info.margin_level,
            currency=info.currency,
        )

    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        if not MT5_AVAILABLE:
            return {"point": 0.00001, "digits": 5, "trade_contract_size": 100000}

        def _fetch():
            return mt5.symbol_info(symbol)

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _fetch)
        if info is None:
            return None
        return {
            "point": info.point,
            "digits": info.digits,
            "trade_contract_size": info.trade_contract_size,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "volume_step": info.volume_step,
        }

    def _generate_sim_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """Generate synthetic OHLCV data for simulation / testing."""
        np.random.seed(abs(hash(symbol + timeframe)) % (2**31))
        base = 1.1000 if "USD" in symbol else 100.0
        periods = pd.date_range(end=datetime.now(tz=timezone.utc), periods=count, freq="1h")
        closes = base + np.cumsum(np.random.randn(count) * 0.001)
        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(count) * 0.001)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(count) * 0.001)
        return pd.DataFrame({
            "open_time": periods,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.random.randint(100, 10000, count).astype(float),
        })

    def _simulate_tick(self, symbol: str) -> TickData:
        import random
        mid = 1.1000 if "USD" in symbol else 100.0
        spread = 0.0002
        return TickData(
            symbol=symbol,
            bid=mid - spread / 2,
            ask=mid + spread / 2,
            last=mid,
            timestamp=datetime.now(tz=timezone.utc),
        )
