"""
Market Data Service

Unified interface for fetching OHLCV data and live prices
across both MT5 (Forex) and Binance (Crypto).
"""

import logging
import asyncio
from typing import Optional, Dict, List
import pandas as pd

from app.execution.mt5_executor import MT5Executor
from app.execution.binance_executor import BinanceExecutor
from app.config import settings

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self):
        self.mt5 = MT5Executor(
            login=settings.MT5_LOGIN,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER,
            path=settings.MT5_PATH,
        )
        self.binance = BinanceExecutor(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=settings.BINANCE_TESTNET,
        )
        self._initialized = False

    async def initialize(self):
        await self.mt5.connect()
        self._initialized = True
        logger.info("MarketDataService initialized")

    async def get_ohlcv(
        self,
        symbol: str,
        market: str,
        timeframe: str = "H1",
        count: int = 200,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV from the appropriate broker."""
        try:
            if market.upper() == "FOREX":
                return await self.mt5.fetch_ohlcv(symbol, timeframe, count)
            elif market.upper() == "CRYPTO":
                return await self.binance.fetch_ohlcv(symbol, timeframe, count)
        except Exception as e:
            logger.error(f"Error fetching OHLCV for {symbol}: {e}")
        return None

    async def get_price(self, symbol: str, market: str) -> Optional[Dict]:
        """Get current bid/ask for a symbol."""
        try:
            if market.upper() == "FOREX":
                return await self.mt5.get_current_price(symbol)
            elif market.upper() == "CRYPTO":
                return await self.binance.get_current_price(symbol)
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
        return None

    async def get_account_summary(self) -> Dict:
        """Aggregate account info from all brokers."""
        mt5_info = await self.mt5.get_account_info()
        binance_info = await self.binance.get_account_info()

        return {
            "mt5": mt5_info,
            "binance": binance_info,
        }

    async def scan_all(
        self,
        forex_symbols: List[str],
        crypto_symbols: List[str],
        timeframe: str = "H1",
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """Fetch OHLCV for all symbols concurrently."""
        tasks = {}

        for sym in forex_symbols:
            tasks[f"FOREX:{sym}"] = self.get_ohlcv(sym, "FOREX", timeframe)
        for sym in crypto_symbols:
            tasks[f"CRYPTO:{sym}"] = self.get_ohlcv(sym, "CRYPTO", timeframe)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        return dict(zip(tasks.keys(), [
            r if not isinstance(r, Exception) else None for r in results
        ]))
