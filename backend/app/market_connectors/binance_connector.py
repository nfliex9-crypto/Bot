import asyncio
from typing import Optional
from datetime import datetime, timezone
import pandas as pd
import numpy as np

from app.market_connectors.base import BaseMarketConnector
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TIMEFRAME_MAP = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H4": "4h", "D1": "1d", "W1": "1w", "MN1": "1M",
}


class BinanceConnector(BaseMarketConnector):
    """Binance connector for cryptocurrency trading."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self._connected = False

    async def connect(self) -> bool:
        try:
            from binance.client import Client

            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: Client(
                    self.settings.binance_api_key,
                    self.settings.binance_api_secret,
                    testnet=self.settings.binance_testnet,
                ),
            )
            self._connected = True
            logger.info("Binance connected successfully", testnet=self.settings.binance_testnet)
            return True
        except ImportError:
            logger.warning("python-binance not installed, running in simulation mode")
            return False
        except Exception as e:
            logger.error("Binance connection failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        if self._client:
            self._client = None
            self._connected = False
            logger.info("Binance disconnected")

    async def get_ohlcv(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> pd.DataFrame:
        if not self._connected or not self._client:
            return self._generate_simulated_data(symbol, count)

        interval = TIMEFRAME_MAP.get(timeframe, "1h")
        loop = asyncio.get_event_loop()

        try:
            klines = await loop.run_in_executor(
                None,
                lambda: self._client.get_klines(
                    symbol=symbol, interval=interval, limit=count
                ),
            )
        except Exception as e:
            logger.error("Failed to fetch Binance klines", error=str(e))
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore",
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _generate_simulated_data(self, symbol: str, count: int) -> pd.DataFrame:
        np.random.seed(42)
        base = 40000.0 if "BTC" in symbol else 2500.0 if "ETH" in symbol else 100.0
        timestamps = pd.date_range(end=datetime.now(timezone.utc), periods=count, freq="h")
        returns = np.random.normal(0, 0.002, count)
        closes = base * np.exp(np.cumsum(returns))
        highs = closes * (1 + np.abs(np.random.normal(0, 0.001, count)))
        lows = closes * (1 - np.abs(np.random.normal(0, 0.001, count)))
        opens = np.roll(closes, 1)
        opens[0] = base
        volumes = np.random.uniform(10, 1000, count)

        return pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

    async def get_current_price(self, symbol: str) -> dict:
        if not self._connected or not self._client:
            return {"bid": 40000.0, "ask": 40001.0, "symbol": symbol, "simulated": True}

        loop = asyncio.get_event_loop()
        try:
            ticker = await loop.run_in_executor(
                None, lambda: self._client.get_ticker(symbol=symbol)
            )
            return {
                "bid": float(ticker["bidPrice"]),
                "ask": float(ticker["askPrice"]),
                "last": float(ticker["lastPrice"]),
                "symbol": symbol,
            }
        except Exception as e:
            logger.error("Failed to get Binance price", error=str(e))
            return {}

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        if not self._connected or not self._client:
            return self._simulated_order_result(symbol, side, volume, "MARKET")

        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=symbol,
                    side=side.upper(),
                    type="MARKET",
                    quantity=volume,
                ),
            )

            result = {
                "success": True,
                "order_id": str(order["orderId"]),
                "price": float(order.get("fills", [{}])[0].get("price", 0)),
                "volume": float(order["executedQty"]),
                "status": order["status"],
            }

            if stop_loss:
                await self._place_stop_loss(symbol, side, volume, stop_loss)
            if take_profit:
                await self._place_take_profit(symbol, side, volume, take_profit)

            return result
        except Exception as e:
            logger.error("Binance market order failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        if not self._connected or not self._client:
            return self._simulated_order_result(symbol, side, volume, "LIMIT")

        loop = asyncio.get_event_loop()
        try:
            order = await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=symbol,
                    side=side.upper(),
                    type="LIMIT",
                    timeInForce="GTC",
                    quantity=volume,
                    price=str(price),
                ),
            )
            return {
                "success": True,
                "order_id": str(order["orderId"]),
                "price": price,
                "volume": volume,
                "status": order["status"],
            }
        except Exception as e:
            logger.error("Binance limit order failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def _place_stop_loss(
        self, symbol: str, side: str, volume: float, stop_price: float
    ) -> dict:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=symbol,
                    side=close_side,
                    type="STOP_MARKET",
                    stopPrice=str(round(stop_price, 2)),
                    quantity=volume,
                    closePosition=True,
                ),
            )
        except Exception as e:
            logger.error("Failed to place stop loss", error=str(e))
            return {"success": False, "error": str(e)}

    async def _place_take_profit(
        self, symbol: str, side: str, volume: float, take_profit: float
    ) -> dict:
        close_side = "SELL" if side.upper() == "BUY" else "BUY"
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=symbol,
                    side=close_side,
                    type="TAKE_PROFIT_MARKET",
                    stopPrice=str(round(take_profit, 2)),
                    quantity=volume,
                    closePosition=True,
                ),
            )
        except Exception as e:
            logger.error("Failed to place take profit", error=str(e))
            return {"success": False, "error": str(e)}

    async def modify_order(
        self,
        order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> dict:
        if not self._connected:
            return {"success": True, "order_id": order_id, "simulated": True}
        logger.info("Binance order modification requires cancel/replace", order_id=order_id)
        return {"success": True, "order_id": order_id, "note": "cancel/replace required"}

    async def close_position(self, order_id: str, volume: Optional[float] = None) -> dict:
        if not self._connected:
            return {"success": True, "order_id": order_id, "simulated": True}

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self._client.cancel_order(symbol="BTCUSDT", orderId=int(order_id)),
            )
            return {"success": True, "order_id": order_id, "status": result.get("status")}
        except Exception as e:
            logger.error("Failed to close Binance position", error=str(e))
            return {"success": False, "error": str(e)}

    async def get_account_info(self) -> dict:
        if not self._connected or not self._client:
            return {
                "balance": 10000.0, "equity": 10000.0, "currency": "USDT",
                "simulated": True,
            }

        loop = asyncio.get_event_loop()
        try:
            account = await loop.run_in_executor(None, self._client.get_account)
            balances = {b["asset"]: float(b["free"]) for b in account["balances"] if float(b["free"]) > 0}
            usdt = balances.get("USDT", 0.0)
            return {
                "balance": usdt,
                "equity": usdt,
                "balances": balances,
                "currency": "USDT",
            }
        except Exception as e:
            logger.error("Failed to get Binance account info", error=str(e))
            return {}

    async def get_open_positions(self) -> list:
        if not self._connected or not self._client:
            return []

        loop = asyncio.get_event_loop()
        try:
            orders = await loop.run_in_executor(
                None, lambda: self._client.get_open_orders()
            )
            return [
                {
                    "order_id": o["orderId"], "symbol": o["symbol"],
                    "side": o["side"].lower(), "volume": float(o["origQty"]),
                    "price": float(o["price"]), "status": o["status"],
                    "type": o["type"],
                }
                for o in orders
            ]
        except Exception as e:
            logger.error("Failed to get Binance open positions", error=str(e))
            return []

    def _simulated_order_result(self, symbol: str, side: str, volume: float, order_type: str):
        import uuid
        base = 40000.0 if "BTC" in symbol else 2500.0
        return {
            "success": True,
            "order_id": str(uuid.uuid4())[:8],
            "price": base,
            "volume": volume,
            "simulated": True,
        }
