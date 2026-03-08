from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import pandas as pd
from loguru import logger

from app.core.config import settings
from app.market_data.base import MarketDataProvider

TIMEFRAME_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}

try:
    from binance.client import Client as BinanceClient
except ImportError:
    BinanceClient = None  # type: ignore[assignment, misc]
    logger.warning("python-binance not available — Binance provider will be degraded")


class BinanceDataProvider(MarketDataProvider):
    """Binance spot / futures data feed."""

    def __init__(self) -> None:
        self._client: BinanceClient | None = None

    async def connect(self) -> bool:
        if BinanceClient is None:
            logger.error("python-binance not installed")
            return False
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: BinanceClient(
                    api_key=settings.binance_api_key,
                    api_secret=settings.binance_api_secret,
                    testnet=settings.binance_testnet,
                ),
            )
            logger.info(
                f"Binance connected (testnet={settings.binance_testnet})"
            )
            return True
        except Exception as exc:
            logger.error(f"Binance connection failed: {exc}")
            return False

    async def disconnect(self) -> None:
        if self._client:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.close_connection)
            self._client = None
            logger.info("Binance disconnected")

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if self._client is None:
            return pd.DataFrame()

        interval = TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            logger.error(f"Unsupported Binance timeframe: {timeframe}")
            return pd.DataFrame()

        loop = asyncio.get_event_loop()

        kwargs: dict = {"symbol": symbol, "interval": interval, "limit": count}
        if start:
            kwargs["startTime"] = int(start.timestamp() * 1000)

        klines = await loop.run_in_executor(
            None, lambda: self._client.get_klines(**kwargs)
        )

        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(
            klines,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for col in ("open", "high", "low", "close", "volume"):
            df[col] = df[col].astype(float)
        return df[["timestamp", "open", "high", "low", "close", "volume"]].copy()

    async def get_current_price(self, symbol: str) -> float:
        if self._client is None:
            return 0.0
        loop = asyncio.get_event_loop()
        ticker = await loop.run_in_executor(
            None, lambda: self._client.get_symbol_ticker(symbol=symbol)
        )
        return float(ticker["price"]) if ticker else 0.0

    async def get_exchange_info(self, symbol: str) -> dict | None:
        if self._client is None:
            return None
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None, lambda: self._client.get_symbol_info(symbol)
        )
        if info is None:
            return None

        step_size = "0.001"
        tick_size = "0.01"
        for f in info.get("filters", []):
            if f["filterType"] == "LOT_SIZE":
                step_size = f["stepSize"]
            elif f["filterType"] == "PRICE_FILTER":
                tick_size = f["tickSize"]

        return {
            "symbol": symbol,
            "step_size": float(step_size),
            "tick_size": float(tick_size),
            "min_notional": 10.0,
        }
