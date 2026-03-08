from __future__ import annotations

import asyncio
from loguru import logger

from app.execution.base import ExecutionEngine, OrderResult

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]


class MT5Executor(ExecutionEngine):
    """Live execution via MetaTrader 5."""

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> OrderResult:
        if mt5 is None:
            return OrderResult(success=False, error="MT5 not available")

        loop = asyncio.get_event_loop()

        order_type = mt5.ORDER_TYPE_BUY if side == "long" else mt5.ORDER_TYPE_SELL
        tick = await loop.run_in_executor(None, lambda: mt5.symbol_info_tick(symbol))
        if tick is None:
            return OrderResult(success=False, error=f"No tick data for {symbol}")

        price = tick.ask if side == "long" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": quantity,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "AI Trading Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        if stop_loss:
            request["sl"] = stop_loss
        if take_profit:
            request["tp"] = take_profit

        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))
        if result is None:
            return OrderResult(success=False, error="MT5 order_send returned None")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(
                success=False,
                error=f"MT5 error {result.retcode}: {result.comment}",
            )

        logger.info(
            f"MT5 order filled: {symbol} {side} {quantity} @ {result.price} "
            f"ticket={result.order}"
        )
        return OrderResult(
            success=True,
            order_id=str(result.order),
            filled_price=result.price,
            filled_qty=quantity,
        )

    async def close_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_id: str | None = None,
    ) -> OrderResult:
        close_side = "short" if side == "long" else "long"
        return await self.place_market_order(symbol, close_side, quantity)

    async def modify_stop_loss(
        self,
        symbol: str,
        order_id: str,
        new_stop_loss: float,
    ) -> OrderResult:
        if mt5 is None:
            return OrderResult(success=False, error="MT5 not available")

        loop = asyncio.get_event_loop()

        positions = await loop.run_in_executor(
            None, lambda: mt5.positions_get(symbol=symbol)
        )
        if not positions:
            return OrderResult(success=False, error=f"No open position for {symbol}")

        pos = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": pos.ticket,
            "sl": new_stop_loss,
            "tp": pos.tp,
        }

        result = await loop.run_in_executor(None, lambda: mt5.order_send(request))
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else "None returned"
            return OrderResult(success=False, error=f"SL modify failed: {error}")

        return OrderResult(success=True, order_id=order_id or "")

    async def get_open_positions(self) -> list[dict]:
        if mt5 is None:
            return []
        loop = asyncio.get_event_loop()
        positions = await loop.run_in_executor(None, mt5.positions_get)
        if not positions:
            return []
        return [
            {
                "symbol": p.symbol,
                "ticket": p.ticket,
                "side": "long" if p.type == 0 else "short",
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit,
            }
            for p in positions
        ]

    async def get_account_balance(self) -> float:
        if mt5 is None:
            return 0.0
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, mt5.account_info)
        return info.balance if info else 0.0
