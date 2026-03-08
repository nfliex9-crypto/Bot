from __future__ import annotations

import asyncio
import logging
from typing import Optional

from config.settings import settings
from core.enums import Direction
from core.models import TradeRecord
from execution.base import BaseExecutor

logger = logging.getLogger(__name__)


class MT5Executor(BaseExecutor):
    """Live forex execution via MetaTrader 5."""

    def __init__(self) -> None:
        self._initialized = False

    async def initialize(self) -> bool:
        try:
            import MetaTrader5 as mt5
            loop = asyncio.get_event_loop()
            kwargs = {}
            if settings.mt5_path:
                kwargs["path"] = settings.mt5_path
            if settings.mt5_login:
                kwargs["login"] = settings.mt5_login
                kwargs["password"] = settings.mt5_password
                kwargs["server"] = settings.mt5_server
            result = await loop.run_in_executor(None, lambda: mt5.initialize(**kwargs))
            self._initialized = result
            if result:
                logger.info("MT5 executor initialized")
            else:
                logger.error("MT5 init failed: %s", mt5.last_error())
            return result
        except ImportError:
            logger.warning("MetaTrader5 not available")
            return False

    async def open_trade(self, trade: TradeRecord) -> Optional[str]:
        if not self._initialized:
            return None
        import MetaTrader5 as mt5

        order_type = mt5.ORDER_TYPE_BUY if trade.direction == Direction.LONG else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": trade.symbol,
            "volume": trade.position_size,
            "type": order_type,
            "price": trade.entry_price,
            "sl": trade.stop_loss,
            "tp": trade.tp3,
            "deviation": 20,
            "magic": 202503,
            "comment": f"AI-Bot {trade.signal_id[:8]}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, mt5.order_send, request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else "No response"
            logger.error("MT5 order failed for %s: %s", trade.symbol, error)
            return None

        logger.info("MT5 order placed: %s ticket=%d", trade.symbol, result.order)
        return str(result.order)

    async def close_trade(self, trade: TradeRecord, reason: str = "") -> bool:
        if not self._initialized:
            return False
        import MetaTrader5 as mt5

        close_type = mt5.ORDER_TYPE_SELL if trade.direction == Direction.LONG else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(trade.symbol)
        price = tick.bid if trade.direction == Direction.LONG else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": trade.symbol,
            "volume": trade.position_size,
            "type": close_type,
            "position": int(trade.broker_order_id),
            "price": price,
            "deviation": 20,
            "magic": 202503,
            "comment": f"Close: {reason}",
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, mt5.order_send, request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("MT5 close failed for %s", trade.symbol)
            return False

        logger.info("MT5 trade closed: %s reason=%s", trade.symbol, reason)
        return True

    async def partial_close(self, trade: TradeRecord, fraction: float) -> bool:
        if not self._initialized:
            return False
        import MetaTrader5 as mt5

        volume = round(trade.position_size * fraction, 2)
        volume = max(0.01, volume)

        close_type = mt5.ORDER_TYPE_SELL if trade.direction == Direction.LONG else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(trade.symbol)
        price = tick.bid if trade.direction == Direction.LONG else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": trade.symbol,
            "volume": volume,
            "type": close_type,
            "position": int(trade.broker_order_id),
            "price": price,
            "deviation": 20,
            "magic": 202503,
            "comment": "Partial close",
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, mt5.order_send, request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("MT5 partial close failed for %s", trade.symbol)
            return False

        trade.position_size -= volume
        return True

    async def modify_sl(self, trade: TradeRecord, new_sl: float) -> bool:
        if not self._initialized:
            return False
        import MetaTrader5 as mt5

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": trade.symbol,
            "position": int(trade.broker_order_id),
            "sl": new_sl,
            "tp": trade.tp3,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, mt5.order_send, request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error("MT5 modify SL failed for %s", trade.symbol)
            return False

        logger.info("MT5 SL modified: %s new_sl=%.5f", trade.symbol, new_sl)
        return True

    async def get_open_pnl(self, trade: TradeRecord, current_price: float) -> float:
        if trade.direction == Direction.LONG:
            return (current_price - trade.entry_price) * trade.position_size * 100000
        else:
            return (trade.entry_price - current_price) * trade.position_size * 100000
