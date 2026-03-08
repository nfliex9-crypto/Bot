"""
Binance trade execution engine.
Handles order placement, modification, and closure for crypto pairs.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import urlencode

import aiohttp

from config.settings import BinanceConfig
from core.logger import get_logger
from core.models import Direction, Trade, TradeSignal, TradeStatus

logger = get_logger("execution.binance")


class BinanceExecutor:
    def __init__(self, config: BinanceConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def base_url(self) -> str:
        return self.config.base_url if self.config.testnet else self.config.live_url

    async def connect(self):
        self._session = aiohttp.ClientSession(
            headers={"X-MBX-APIKEY": self.config.api_key}
        )

    async def disconnect(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params)
        sig = hmac.new(
            self.config.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = sig
        return params

    async def place_order(self, signal: TradeSignal, quantity: float) -> Optional[Trade]:
        """Place a market order on Binance."""
        if not self._session:
            await self.connect()

        try:
            side = "BUY" if signal.direction == Direction.LONG else "SELL"
            params = self._sign({
                "symbol": signal.symbol,
                "side": side,
                "type": "MARKET",
                "quantity": f"{quantity:.6f}",
                "newOrderRespType": "FULL",
            })

            async with self._session.post(
                f"{self.base_url}/api/v3/order", params=params
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    logger.error(f"Binance order error: {data}")
                    return None

                fill_price = float(data.get("fills", [{}])[0].get("price", signal.entry_price))

                trade = Trade(
                    signal=signal,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    entry_price=fill_price,
                    stop_loss=signal.stop_loss,
                    tp1=signal.tp1,
                    tp2=signal.tp2,
                    tp3=signal.tp3,
                    position_size=quantity,
                    status=TradeStatus.OPEN,
                    broker_order_id=str(data.get("orderId", "")),
                    market="crypto",
                )

                logger.info(
                    f"Binance order filled: {trade.trade_id} {signal.symbol} "
                    f"{side} {quantity} @ {fill_price}"
                )

                await self._place_oco_if_possible(signal, quantity, fill_price)
                return trade

        except Exception as e:
            logger.error(f"Binance execution error: {e}")
            return None

    async def _place_oco_if_possible(
        self, signal: TradeSignal, quantity: float, fill_price: float
    ):
        """Attempt to place OCO (SL + TP) after market fill."""
        try:
            if signal.direction == Direction.LONG:
                side = "SELL"
                stop_price = signal.stop_loss
                limit_price = signal.stop_loss * 0.999
                tp_price = signal.tp3
            else:
                side = "BUY"
                stop_price = signal.stop_loss
                limit_price = signal.stop_loss * 1.001
                tp_price = signal.tp3

            params = self._sign({
                "symbol": signal.symbol,
                "side": side,
                "quantity": f"{quantity:.6f}",
                "price": f"{tp_price:.2f}",
                "stopPrice": f"{stop_price:.2f}",
                "stopLimitPrice": f"{limit_price:.2f}",
                "stopLimitTimeInForce": "GTC",
            })

            async with self._session.post(
                f"{self.base_url}/api/v3/order/oco", params=params
            ) as resp:
                if resp.status == 200:
                    logger.info(f"OCO placed for {signal.symbol}")
                else:
                    data = await resp.json()
                    logger.warning(f"OCO failed (will manage manually): {data}")

        except Exception as e:
            logger.warning(f"OCO placement error: {e}")

    async def close_position(self, trade: Trade, quantity: Optional[float] = None) -> bool:
        """Close or partially close a position."""
        if not self._session:
            return False

        try:
            side = "SELL" if trade.direction == Direction.LONG else "BUY"
            qty = quantity if quantity else trade.position_size

            params = self._sign({
                "symbol": trade.symbol,
                "side": side,
                "type": "MARKET",
                "quantity": f"{qty:.6f}",
            })

            async with self._session.post(
                f"{self.base_url}/api/v3/order", params=params
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Binance position closed: {trade.trade_id} qty={qty}")
                    return True
                data = await resp.json()
                logger.error(f"Close failed: {data}")
                return False
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return False
