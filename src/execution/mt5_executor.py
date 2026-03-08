"""
MetaTrader5 trade execution engine.
Handles both paper (simulated) and live order placement via MT5 API.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from loguru import logger

from src.execution.base_executor import BaseExecutor, OrderResult, CloseResult

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

# Paper trade store (in-memory for simulation)
_PAPER_POSITIONS: dict = {}


class MT5Executor(BaseExecutor):
    """
    Executes trades on MetaTrader5.
    In paper mode: simulates orders and tracks P&L in memory.
    In live mode: places real orders via MT5 API.
    """

    def __init__(self, paper_mode: bool = True):
        super().__init__("MT5", paper_mode=paper_mode)

    async def open_trade(
        self,
        symbol: str,
        direction: str,
        lot_size: float,
        entry_price: Optional[float],
        stop_loss: float,
        tp1: float,
        comment: str = "AI_BOT",
    ) -> OrderResult:
        if self.paper_mode:
            return await self._paper_open(symbol, direction, lot_size, entry_price, stop_loss, tp1)

        if not MT5_AVAILABLE:
            return OrderResult(
                success=False, broker_ticket=None, executed_price=None,
                executed_qty=None, commission=0.0, swap=0.0,
                error="MT5 not available on this platform",
            )

        return await self._live_open(symbol, direction, lot_size, entry_price, stop_loss, tp1, comment)

    async def close_trade(
        self,
        broker_ticket: str,
        symbol: str,
        lot_size: float,
        direction: str,
        close_price: Optional[float] = None,
    ) -> CloseResult:
        if self.paper_mode:
            return await self._paper_close(broker_ticket, symbol, close_price)
        return await self._live_close(broker_ticket, symbol, lot_size, direction, close_price)

    async def modify_stop_loss(
        self, broker_ticket: str, symbol: str, new_stop_loss: float
    ) -> bool:
        if self.paper_mode:
            if broker_ticket in _PAPER_POSITIONS:
                _PAPER_POSITIONS[broker_ticket]["stop_loss"] = new_stop_loss
                logger.info(f"[PAPER] SL modified | ticket={broker_ticket} new_sl={new_stop_loss}")
                return True
            return False

        if not MT5_AVAILABLE:
            return False

        def _modify():
            ticket_int = int(broker_ticket)
            positions = mt5.positions_get(ticket=ticket_int)
            if not positions:
                return False
            pos = positions[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "sl": new_stop_loss,
                "tp": pos.tp,
                "position": ticket_int,
            }
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _modify)

    async def get_open_positions(self) -> List[dict]:
        if self.paper_mode:
            return [
                {
                    "ticket": ticket,
                    "symbol": pos["symbol"],
                    "direction": pos["direction"],
                    "lot_size": pos["lot_size"],
                    "entry_price": pos["entry_price"],
                    "stop_loss": pos["stop_loss"],
                    "tp1": pos["tp1"],
                    "open_time": pos["open_time"],
                }
                for ticket, pos in _PAPER_POSITIONS.items()
            ]

        if not MT5_AVAILABLE:
            return []

        def _fetch():
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [
                {
                    "ticket": str(p.ticket),
                    "symbol": p.symbol,
                    "direction": "long" if p.type == 0 else "short",
                    "lot_size": p.volume,
                    "entry_price": p.price_open,
                    "stop_loss": p.sl,
                    "tp1": p.tp,
                    "open_time": datetime.fromtimestamp(p.time, tz=timezone.utc),
                }
                for p in positions
            ]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch)

    # ── Paper Trading ─────────────────────────────────────────────────────────

    async def _paper_open(
        self, symbol: str, direction: str, lot_size: float,
        entry_price: Optional[float], stop_loss: float, tp1: float
    ) -> OrderResult:
        ticket = str(uuid.uuid4())[:8].upper()
        price = entry_price or 0.0
        _PAPER_POSITIONS[ticket] = {
            "symbol": symbol,
            "direction": direction,
            "lot_size": lot_size,
            "entry_price": price,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "open_time": datetime.now(tz=timezone.utc),
        }
        logger.info(
            f"[PAPER/FOREX] TRADE OPEN | {symbol} {direction.upper()} | "
            f"lot={lot_size} entry={price} sl={stop_loss} tp1={tp1} ticket={ticket}"
        )
        return OrderResult(
            success=True,
            broker_ticket=ticket,
            executed_price=price,
            executed_qty=lot_size,
            commission=0.0,
            swap=0.0,
            error=None,
        )

    async def _paper_close(
        self, broker_ticket: str, symbol: str, close_price: Optional[float]
    ) -> CloseResult:
        pos = _PAPER_POSITIONS.pop(broker_ticket, None)
        if pos is None:
            return CloseResult(success=False, close_price=None, pnl=None,
                               commission=0.0, error="Position not found")

        close = close_price or pos["entry_price"]
        direction = pos["direction"]

        if direction == "long":
            pips = (close - pos["entry_price"]) / 0.0001
        else:
            pips = (pos["entry_price"] - close) / 0.0001

        pip_value = 10.0  # ~$10 per pip per standard lot for USD pairs
        pnl = round(pips * pip_value * pos["lot_size"], 2)

        logger.info(
            f"[PAPER/FOREX] TRADE CLOSE | {symbol} | "
            f"close={close} pnl={pnl} ticket={broker_ticket}"
        )
        return CloseResult(success=True, close_price=close, pnl=pnl, commission=0.0, error=None)

    # ── Live Trading ──────────────────────────────────────────────────────────

    async def _live_open(
        self, symbol: str, direction: str, lot_size: float,
        entry_price: Optional[float], stop_loss: float, tp1: float, comment: str
    ) -> OrderResult:
        def _send():
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return None, "Symbol not found"

            order_type = mt5.ORDER_TYPE_BUY if direction == "long" else mt5.ORDER_TYPE_SELL
            tick = mt5.symbol_info_tick(symbol)
            price = tick.ask if direction == "long" else tick.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": order_type,
                "price": price,
                "sl": stop_loss,
                "tp": tp1,
                "deviation": 20,
                "magic": 20240101,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            return result, None

        loop = asyncio.get_event_loop()
        result, err = await loop.run_in_executor(None, _send)

        if err:
            return OrderResult(success=False, broker_ticket=None, executed_price=None,
                               executed_qty=None, commission=0.0, swap=0.0, error=err)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=False, broker_ticket=None, executed_price=None,
                               executed_qty=None, commission=0.0, swap=0.0,
                               error=f"MT5 error {result.retcode}: {result.comment}")

        logger.info(
            f"[LIVE/FOREX] TRADE OPEN | {symbol} {direction.upper()} | "
            f"lot={lot_size} price={result.price} ticket={result.order}"
        )
        return OrderResult(
            success=True,
            broker_ticket=str(result.order),
            executed_price=result.price,
            executed_qty=lot_size,
            commission=0.0,
            swap=0.0,
            error=None,
        )

    async def _live_close(
        self, broker_ticket: str, symbol: str, lot_size: float,
        direction: str, close_price: Optional[float]
    ) -> CloseResult:
        def _close():
            ticket_int = int(broker_ticket)
            positions = mt5.positions_get(ticket=ticket_int)
            if not positions:
                return None, "Position not found"

            pos = positions[0]
            close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
            tick = mt5.symbol_info_tick(symbol)
            price = tick.bid if pos.type == 0 else tick.ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": ticket_int,
                "price": price,
                "deviation": 20,
                "magic": 20240101,
                "comment": "AI_BOT_CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            return result, None

        loop = asyncio.get_event_loop()
        result, err = await loop.run_in_executor(None, _close)

        if err:
            return CloseResult(success=False, close_price=None, pnl=None,
                               commission=0.0, error=err)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return CloseResult(success=False, close_price=None, pnl=None,
                               commission=0.0, error=f"MT5 error: {result.comment}")

        logger.info(f"[LIVE/FOREX] TRADE CLOSE | {symbol} ticket={broker_ticket}")
        return CloseResult(success=True, close_price=result.price, pnl=None,
                           commission=0.0, error=None)
