"""
MetaTrader 5 trade execution engine.
Handles order placement, modification, and closure for forex pairs.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from config.settings import MT5Config
from core.logger import get_logger
from core.models import Direction, OrderType, Trade, TradeSignal, TradeStatus

logger = get_logger("execution.mt5")

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


class MT5Executor:
    def __init__(self, config: MT5Config):
        self.config = config

    async def place_order(self, signal: TradeSignal, lot_size: float) -> Optional[Trade]:
        """Place a market order on MT5."""
        if not MT5_AVAILABLE:
            logger.error("MT5 not available for execution")
            return None

        try:
            order_type = mt5.ORDER_TYPE_BUY if signal.direction == Direction.LONG else mt5.ORDER_TYPE_SELL
            symbol_info = mt5.symbol_info(signal.symbol)
            if symbol_info is None:
                logger.error(f"Symbol {signal.symbol} not found")
                return None

            if not symbol_info.visible:
                mt5.symbol_select(signal.symbol, True)

            price = mt5.symbol_info_tick(signal.symbol)
            if price is None:
                return None

            fill_price = price.ask if signal.direction == Direction.LONG else price.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": signal.symbol,
                "volume": lot_size,
                "type": order_type,
                "price": fill_price,
                "sl": signal.stop_loss,
                "tp": signal.tp3,
                "deviation": 20,
                "magic": 20250308,
                "comment": f"AI_BOT_{signal.signal_id}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = await asyncio.to_thread(mt5.order_send, request)

            if result is None:
                logger.error(f"MT5 order_send returned None for {signal.symbol}")
                return None

            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"MT5 order failed: {result.retcode} — {result.comment}")
                return None

            trade = Trade(
                signal=signal,
                symbol=signal.symbol,
                direction=signal.direction,
                entry_price=result.price,
                stop_loss=signal.stop_loss,
                tp1=signal.tp1,
                tp2=signal.tp2,
                tp3=signal.tp3,
                position_size=lot_size,
                status=TradeStatus.OPEN,
                broker_order_id=str(result.order),
                market="forex",
            )

            logger.info(
                f"MT5 order filled: {trade.trade_id} {signal.symbol} "
                f"{signal.direction.value} {lot_size} lots @ {result.price}"
            )
            return trade

        except Exception as e:
            logger.error(f"MT5 execution error: {e}")
            return None

    async def modify_sl(self, trade: Trade, new_sl: float) -> bool:
        """Modify stop loss for an open position."""
        if not MT5_AVAILABLE:
            return False

        try:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": trade.symbol,
                "sl": new_sl,
                "tp": trade.tp3,
                "position": int(trade.broker_order_id),
            }
            result = await asyncio.to_thread(mt5.order_send, request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"SL modified for {trade.trade_id}: {new_sl:.5f}")
                return True
            logger.error(f"SL modify failed: {result.retcode if result else 'None'}")
            return False
        except Exception as e:
            logger.error(f"SL modify error: {e}")
            return False

    async def close_position(self, trade: Trade, volume: Optional[float] = None) -> bool:
        """Close or partially close a position."""
        if not MT5_AVAILABLE:
            return False

        try:
            close_type = mt5.ORDER_TYPE_SELL if trade.direction == Direction.LONG else mt5.ORDER_TYPE_BUY
            price_info = mt5.symbol_info_tick(trade.symbol)
            if price_info is None:
                return False

            close_price = price_info.bid if trade.direction == Direction.LONG else price_info.ask
            close_vol = volume if volume else trade.position_size

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": trade.symbol,
                "volume": close_vol,
                "type": close_type,
                "price": close_price,
                "deviation": 20,
                "magic": 20250308,
                "comment": f"CLOSE_{trade.trade_id}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "position": int(trade.broker_order_id),
            }

            result = await asyncio.to_thread(mt5.order_send, request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Position closed: {trade.trade_id} vol={close_vol}")
                return True
            logger.error(f"Close failed: {result.retcode if result else 'None'}")
            return False
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return False
