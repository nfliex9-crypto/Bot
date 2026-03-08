from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.models import Market
from execution.base_executor import BaseExecutor
from utils.logger import get_logger

logger = get_logger(__name__)

# Number of bars to keep per symbol/timeframe in the rolling buffer
BUFFER_SIZES = {
    settings.bias_timeframe: 300,    # H1
    settings.trend_timeframe: 500,   # M15
    settings.entry_timeframe: 500,   # M5
}

_SymbolKey = Tuple[str, str]   # (symbol, timeframe)


class DataFeed:
    """
    Manages rolling OHLCV buffers for multiple symbols and timeframes.

    Each call to refresh() fetches the latest bars from the executor
    and appends them to the in-memory buffer, keeping only the
    configured number of bars to control memory usage.
    """

    def __init__(self, executor: BaseExecutor) -> None:
        self._executor = executor
        self._buffers: Dict[_SymbolKey, pd.DataFrame] = {}

    # ------------------------------------------------------------------
    async def initialise(self, symbols: list[str], timeframes: list[str]) -> None:
        """Perform the initial historical data load for all symbols/timeframes."""
        tasks = [
            self._load(symbol, tf, limit=BUFFER_SIZES.get(tf, 500))
            for symbol in symbols
            for tf in timeframes
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(
            "DataFeed initialised: %d symbol×timeframe buffers",
            len(self._buffers),
        )

    async def refresh(self, symbol: str, timeframe: str) -> None:
        """Fetch and append the latest bars to the buffer."""
        await self._load(symbol, timeframe, limit=50)

    async def get(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Returns the current buffer for the given symbol/timeframe."""
        key: _SymbolKey = (symbol, timeframe)
        if key not in self._buffers:
            await self._load(symbol, timeframe, limit=BUFFER_SIZES.get(timeframe, 500))
        return self._buffers.get(key, pd.DataFrame())

    # ------------------------------------------------------------------
    async def _load(self, symbol: str, timeframe: str, limit: int) -> None:
        key: _SymbolKey = (symbol, timeframe)
        try:
            new_bars = await self._executor.fetch_ohlcv(symbol, timeframe, limit=limit)
            if new_bars.empty:
                return

            existing = self._buffers.get(key, pd.DataFrame())
            if existing.empty:
                self._buffers[key] = new_bars
            else:
                combined = pd.concat([existing, new_bars])
                combined = combined[~combined.index.duplicated(keep="last")]
                max_bars = BUFFER_SIZES.get(timeframe, 500)
                self._buffers[key] = combined.sort_index().iloc[-max_bars:]

        except Exception as exc:
            logger.warning(
                "DataFeed._load failed for %s %s: %s", symbol, timeframe, exc
            )

    def clear(self, symbol: Optional[str] = None) -> None:
        if symbol:
            for tf in list(BUFFER_SIZES.keys()):
                self._buffers.pop((symbol, tf), None)
        else:
            self._buffers.clear()
