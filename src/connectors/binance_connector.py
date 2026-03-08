"""
Binance market data and trading connector.
Uses python-binance with async support.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, List
import pandas as pd
import numpy as np
from loguru import logger

from src.connectors.base import BaseConnector, TickData, AccountInfo
from config.settings import settings

try:
    from binance import AsyncClient, Client
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    AsyncClient = None
    Client = None
    BinanceAPIException = Exception
    BINANCE_AVAILABLE = False
    logger.warning("python-binance package not available")

BINANCE_TIMEFRAME_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}


class BinanceConnector(BaseConnector):
    """Async connector for Binance spot/futures market data."""

    def __init__(self):
        super().__init__("Binance")
        self._client: Optional[object] = None

    async def connect(self) -> bool:
        if not BINANCE_AVAILABLE:
            logger.warning("Binance client not available – running in simulation mode")
            self._connected = True
            return True

        try:
            self._client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_secret_key,
                testnet=settings.binance_testnet,
            )
            info = await self._client.get_server_time()
            logger.info(f"Binance connected | server_time={info['serverTime']}")
            self._connected = True
        except Exception as e:
            logger.error(f"Binance connection failed: {e}")
            self._connected = False
        return self._connected

    async def disconnect(self) -> None:
        if self._client and BINANCE_AVAILABLE:
            await self._client.close_connection()
        self._connected = False
        logger.info("Binance disconnected")

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        count: int = 500,
        start: Optional[datetime] = None,
    ) -> pd.DataFrame:
        if not BINANCE_AVAILABLE or not self._client:
            return self._generate_sim_ohlcv(symbol, timeframe, count)

        tf = BINANCE_TIMEFRAME_MAP.get(timeframe, "1h")
        try:
            if start:
                start_ms = int(start.timestamp() * 1000)
                klines = await self._client.get_historical_klines(
                    symbol, tf, start_str=start_ms, limit=count
                )
            else:
                klines = await self._client.get_klines(
                    symbol=symbol, interval=tf, limit=count
                )
        except BinanceAPIException as e:
            logger.error(f"Binance OHLCV error for {symbol}: {e}")
            return pd.DataFrame()

        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
        df = df.sort_values("open_time").reset_index(drop=True)
        return df

    async def get_tick(self, symbol: str) -> Optional[TickData]:
        if not BINANCE_AVAILABLE or not self._client:
            return self._simulate_tick(symbol)

        try:
            ticker = await self._client.get_orderbook_ticker(symbol=symbol)
            price = await self._client.get_symbol_ticker(symbol=symbol)
            return TickData(
                symbol=symbol,
                bid=float(ticker["bidPrice"]),
                ask=float(ticker["askPrice"]),
                last=float(price["price"]),
                timestamp=datetime.now(tz=timezone.utc),
            )
        except BinanceAPIException as e:
            logger.error(f"Binance tick error for {symbol}: {e}")
            return None

    async def get_account_info(self) -> Optional[AccountInfo]:
        if not BINANCE_AVAILABLE or not self._client:
            return AccountInfo(
                balance=settings.account_balance,
                equity=settings.account_balance,
                margin=0.0,
                free_margin=settings.account_balance,
                margin_level=0.0,
                currency="USDT",
            )

        try:
            account = await self._client.get_account()
            usdt_balance = 0.0
            for asset in account.get("balances", []):
                if asset["asset"] == "USDT":
                    usdt_balance = float(asset["free"]) + float(asset["locked"])
                    break
            return AccountInfo(
                balance=usdt_balance,
                equity=usdt_balance,
                margin=0.0,
                free_margin=usdt_balance,
                margin_level=0.0,
                currency="USDT",
            )
        except BinanceAPIException as e:
            logger.error(f"Binance account info error: {e}")
            return None

    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        if not BINANCE_AVAILABLE or not self._client:
            return {"min_qty": 0.001, "step_size": 0.001, "min_notional": 10.0}

        try:
            info = await self._client.get_symbol_info(symbol)
            if not info:
                return None
            filters = {f["filterType"]: f for f in info.get("filters", [])}
            lot = filters.get("LOT_SIZE", {})
            notional = filters.get("MIN_NOTIONAL", {})
            return {
                "min_qty": float(lot.get("minQty", 0.001)),
                "max_qty": float(lot.get("maxQty", 9999.0)),
                "step_size": float(lot.get("stepSize", 0.001)),
                "min_notional": float(notional.get("minNotional", 10.0)),
            }
        except BinanceAPIException as e:
            logger.error(f"Binance symbol info error for {symbol}: {e}")
            return None

    def _generate_sim_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        np.random.seed(abs(hash(symbol + timeframe)) % (2**31))
        base = 50000.0 if "BTC" in symbol else 3000.0 if "ETH" in symbol else 100.0
        periods = pd.date_range(end=datetime.now(tz=timezone.utc), periods=count, freq="1h")
        closes = base + np.cumsum(np.random.randn(count) * base * 0.005)
        closes = np.maximum(closes, base * 0.1)
        opens = np.roll(closes, 1)
        opens[0] = closes[0]
        highs = np.maximum(opens, closes) + np.abs(np.random.randn(count) * closes * 0.005)
        lows = np.minimum(opens, closes) - np.abs(np.random.randn(count) * closes * 0.005)
        return pd.DataFrame({
            "open_time": periods,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": np.random.uniform(100, 10000, count),
        })

    def _simulate_tick(self, symbol: str) -> TickData:
        base = 50000.0 if "BTC" in symbol else 3000.0 if "ETH" in symbol else 100.0
        spread = base * 0.0002
        return TickData(
            symbol=symbol,
            bid=base - spread / 2,
            ask=base + spread / 2,
            last=base,
            timestamp=datetime.now(tz=timezone.utc),
        )
