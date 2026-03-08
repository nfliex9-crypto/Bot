"""
Binance market data provider for crypto pairs.
Supports both testnet and live endpoints.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

import aiohttp
import pandas as pd

from config.settings import BinanceConfig
from core.logger import get_logger

logger = get_logger("data.binance")

TIMEFRAME_MAP = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "4h", "D1": "1d",
}


class BinanceDataProvider:
    def __init__(self, config: BinanceConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False

    @property
    def base_url(self) -> str:
        if self.config.testnet:
            return self.config.base_url
        return self.config.live_url

    async def connect(self) -> bool:
        try:
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self.config.api_key}
            )
            async with self._session.get(f"{self.base_url}/api/v3/ping") as resp:
                if resp.status == 200:
                    self._connected = True
                    logger.info(f"Binance connected (testnet={self.config.testnet})")
                    return True
                logger.error(f"Binance ping failed: {resp.status}")
                return False
        except Exception as e:
            logger.error(f"Binance connection error: {e}")
            return False

    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
        logger.info("Binance disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        signature = hmac.new(
            self.config.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    async def get_candles(
        self, symbol: str, timeframe: str, limit: int = 500
    ) -> pd.DataFrame:
        if not self._connected or not self._session:
            return self._empty_df()

        interval = TIMEFRAME_MAP.get(timeframe, "5m")
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        try:
            async with self._session.get(
                f"{self.base_url}/api/v3/klines", params=params
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Binance klines error {resp.status}: {await resp.text()}")
                    return self._empty_df()

                data = await resp.json()
                if not data:
                    return self._empty_df()

                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_vol", "trades", "taker_buy_base",
                    "taker_buy_quote", "ignore",
                ])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)
                df["symbol"] = symbol
                df["timeframe"] = timeframe
                return df[["timestamp", "open", "high", "low", "close", "volume", "symbol", "timeframe"]]
        except Exception as e:
            logger.error(f"Error fetching Binance candles for {symbol}: {e}")
            return self._empty_df()

    async def get_current_price(self, symbol: str) -> Optional[dict]:
        if not self._connected or not self._session:
            return None
        try:
            async with self._session.get(
                f"{self.base_url}/api/v3/ticker/price", params={"symbol": symbol}
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                price = float(data["price"])
                return {"bid": price, "ask": price, "last": price, "time": datetime.utcnow()}
        except Exception as e:
            logger.error(f"Error getting Binance price for {symbol}: {e}")
            return None

    async def get_account_balance(self) -> Optional[dict]:
        if not self._connected or not self._session:
            return None
        try:
            params = self._sign({})
            async with self._session.get(
                f"{self.base_url}/api/v3/account", params=params
            ) as resp:
                if resp.status != 200:
                    logger.error(f"Binance account error: {await resp.text()}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.error(f"Error getting Binance account: {e}")
            return None

    def _empty_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume", "symbol", "timeframe"]
        )
