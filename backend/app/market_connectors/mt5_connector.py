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
    "M1": 1, "M5": 5, "M15": 15, "M30": 30,
    "H1": 16385, "H4": 16388, "D1": 16408, "W1": 32769, "MN1": 49153,
}


class MT5Connector(BaseMarketConnector):
    """MetaTrader 5 connector for Forex trading."""

    def __init__(self):
        self.settings = get_settings()
        self._connected = False
        self._mt5 = None

    def _get_mt5(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5
                self._mt5 = mt5
            except ImportError:
                logger.warning("MetaTrader5 not available on this platform")
                return None
        return self._mt5

    async def connect(self) -> bool:
        mt5 = self._get_mt5()
        if mt5 is None:
            logger.warning("MT5 module not available, running in simulation mode")
            self._connected = False
            return False

        loop = asyncio.get_event_loop()
        initialized = await loop.run_in_executor(None, mt5.initialize, self.settings.mt5_path)
        if not initialized:
            logger.error("MT5 initialization failed", error=mt5.last_error())
            return False

        authorized = await loop.run_in_executor(
            None,
            lambda: mt5.login(
                self.settings.mt5_login,
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
            ),
        )
        if not authorized:
            logger.error("MT5 login failed", error=mt5.last_error())
            return False

        self._connected = True
        logger.info("MT5 connected successfully")
        return True

    async def disconnect(self) -> None:
        mt5 = self._get_mt5()
        if mt5 and self._connected:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mt5.shutdown)
            self._connected = False
            logger.info("MT5 disconnected")

    async def get_ohlcv(
        self, symbol: str, timeframe: str, count: int = 500
    ) -> pd.DataFrame:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return self._generate_simulated_data(symbol, timeframe, count)

        tf = TIMEFRAME_MAP.get(timeframe, 16385)
        loop = asyncio.get_event_loop()
        rates = await loop.run_in_executor(
            None, lambda: mt5.copy_rates_from_pos(symbol, tf, 0, count)
        )

        if rates is None or len(rates) == 0:
            logger.warning("No data received from MT5", symbol=symbol, timeframe=timeframe)
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.rename(columns={
            "time": "timestamp", "tick_volume": "volume"
        }, inplace=True)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _generate_simulated_data(
        self, symbol: str, timeframe: str, count: int
    ) -> pd.DataFrame:
        np.random.seed(42)
        base_price = 1.1000 if "EUR" in symbol else 150.0
        timestamps = pd.date_range(end=datetime.now(timezone.utc), periods=count, freq="h")
        returns = np.random.normal(0, 0.001, count)
        closes = base_price * np.exp(np.cumsum(returns))
        highs = closes * (1 + np.abs(np.random.normal(0, 0.0005, count)))
        lows = closes * (1 - np.abs(np.random.normal(0, 0.0005, count)))
        opens = np.roll(closes, 1)
        opens[0] = base_price
        volumes = np.random.randint(100, 10000, count).astype(float)

        return pd.DataFrame({
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })

    async def get_current_price(self, symbol: str) -> dict:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return {"bid": 1.1000, "ask": 1.1002, "symbol": symbol}

        loop = asyncio.get_event_loop()
        tick = await loop.run_in_executor(None, lambda: mt5.symbol_info_tick(symbol))
        if tick is None:
            return {}
        return {"bid": tick.bid, "ask": tick.ask, "symbol": symbol, "time": tick.time}

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        comment: str = "",
    ) -> dict:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return self._simulated_order_result(symbol, side, volume, "market")

        price_info = await self.get_current_price(symbol)
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        price = price_info["ask"] if side == "buy" else price_info["bid"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": comment or "AI Trading System",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if stop_loss:
            request["sl"] = stop_loss
        if take_profit:
            request["tp"] = take_profit

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("MT5 order failed", retcode=result.retcode, comment=result.comment)
            return {"success": False, "error": result.comment, "retcode": result.retcode}

        logger.info("MT5 order placed", order_id=result.order, symbol=symbol, side=side)
        return {
            "success": True,
            "order_id": str(result.order),
            "price": result.price,
            "volume": result.volume,
        }

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
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return self._simulated_order_result(symbol, side, volume, "limit")

        order_type = mt5.ORDER_TYPE_BUY_LIMIT if side == "buy" else mt5.ORDER_TYPE_SELL_LIMIT
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": comment or "AI Trading System",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        if stop_loss:
            request["sl"] = stop_loss
        if take_profit:
            request["tp"] = take_profit

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": result.comment}

        return {"success": True, "order_id": str(result.order), "price": price, "volume": volume}

    async def modify_order(
        self,
        order_id: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> dict:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return {"success": True, "order_id": order_id, "simulated": True}

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(order_id),
        }
        if stop_loss is not None:
            request["sl"] = stop_loss
        if take_profit is not None:
            request["tp"] = take_profit

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": result.comment}
        return {"success": True, "order_id": order_id}

    async def close_position(self, order_id: str, volume: Optional[float] = None) -> dict:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return {"success": True, "order_id": order_id, "simulated": True}

        loop = asyncio.get_event_loop()
        position = await loop.run_in_executor(
            None, lambda: mt5.positions_get(ticket=int(order_id))
        )
        if not position:
            return {"success": False, "error": "Position not found"}

        pos = position[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        price_info = await self.get_current_price(pos.symbol)
        price = price_info["bid"] if pos.type == 0 else price_info["ask"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": volume or pos.volume,
            "type": close_type,
            "position": int(order_id),
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Close by AI Trading System",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"success": False, "error": result.comment}
        return {"success": True, "order_id": order_id, "close_price": result.price}

    async def get_account_info(self) -> dict:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return {
                "balance": 10000.0, "equity": 10000.0, "margin": 0.0,
                "free_margin": 10000.0, "leverage": 100, "currency": "USD",
                "simulated": True,
            }

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, mt5.account_info)
        if info is None:
            return {}
        return {
            "balance": info.balance, "equity": info.equity, "margin": info.margin,
            "free_margin": info.margin_free, "leverage": info.leverage,
            "currency": info.currency, "profit": info.profit,
        }

    async def get_open_positions(self) -> list:
        mt5 = self._get_mt5()
        if not mt5 or not self._connected:
            return []

        loop = asyncio.get_event_loop()
        positions = await loop.run_in_executor(None, mt5.positions_get)
        if positions is None:
            return []

        return [
            {
                "ticket": p.ticket, "symbol": p.symbol, "type": "buy" if p.type == 0 else "sell",
                "volume": p.volume, "price_open": p.price_open, "sl": p.sl, "tp": p.tp,
                "profit": p.profit, "swap": p.swap, "time": p.time,
            }
            for p in positions
        ]

    def _simulated_order_result(self, symbol: str, side: str, volume: float, order_type: str):
        import uuid
        return {
            "success": True,
            "order_id": str(uuid.uuid4())[:8],
            "price": 1.1000 if side == "buy" else 1.0998,
            "volume": volume,
            "simulated": True,
        }
