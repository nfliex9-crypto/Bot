from __future__ import annotations

import asyncio
import logging
from typing import Optional

from config.settings import settings
from core.enums import Direction
from core.models import TradeRecord
from execution.base import BaseExecutor

logger = logging.getLogger(__name__)


class BinanceExecutor(BaseExecutor):
    """Live crypto execution via Binance spot API."""

    def __init__(self) -> None:
        self._client = None

    async def initialize(self) -> bool:
        try:
            from binance.client import Client
            if settings.binance_testnet:
                self._client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=True,
                )
            else:
                self._client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                )
            logger.info("Binance executor initialized (testnet=%s)", settings.binance_testnet)
            return True
        except Exception:
            logger.exception("Binance executor init failed")
            return False

    async def open_trade(self, trade: TradeRecord) -> Optional[str]:
        if self._client is None:
            return None

        side = "BUY" if trade.direction == Direction.LONG else "SELL"
        loop = asyncio.get_event_loop()

        try:
            order = await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="MARKET",
                    quantity=self._format_qty(trade.symbol, trade.position_size),
                ),
            )
            order_id = str(order["orderId"])
            fill_price = float(order.get("fills", [{}])[0].get("price", trade.entry_price))
            trade.entry_price = fill_price
            logger.info("Binance order: %s %s qty=%.6f id=%s", side, trade.symbol, trade.position_size, order_id)
            return order_id
        except Exception:
            logger.exception("Binance order failed for %s", trade.symbol)
            return None

    async def close_trade(self, trade: TradeRecord, reason: str = "") -> bool:
        if self._client is None:
            return False

        side = "SELL" if trade.direction == Direction.LONG else "BUY"
        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="MARKET",
                    quantity=self._format_qty(trade.symbol, trade.position_size),
                ),
            )
            logger.info("Binance close: %s reason=%s", trade.symbol, reason)
            return True
        except Exception:
            logger.exception("Binance close failed for %s", trade.symbol)
            return False

    async def partial_close(self, trade: TradeRecord, fraction: float) -> bool:
        if self._client is None:
            return False

        close_qty = trade.position_size * fraction
        side = "SELL" if trade.direction == Direction.LONG else "BUY"
        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=trade.symbol,
                    side=side,
                    type="MARKET",
                    quantity=self._format_qty(trade.symbol, close_qty),
                ),
            )
            trade.position_size -= close_qty
            return True
        except Exception:
            logger.exception("Binance partial close failed for %s", trade.symbol)
            return False

    async def modify_sl(self, trade: TradeRecord, new_sl: float) -> bool:
        trade.stop_loss = new_sl
        logger.info("Binance SL updated in memory: %s sl=%.2f (manual monitoring)", trade.symbol, new_sl)
        return True

    async def get_open_pnl(self, trade: TradeRecord, current_price: float) -> float:
        if trade.direction == Direction.LONG:
            return (current_price - trade.entry_price) * trade.position_size
        else:
            return (trade.entry_price - current_price) * trade.position_size

    @staticmethod
    def _format_qty(symbol: str, qty: float) -> str:
        upper = symbol.upper()
        if "BTC" in upper:
            return f"{qty:.5f}"
        elif "ETH" in upper:
            return f"{qty:.4f}"
        else:
            return f"{qty:.3f}"
