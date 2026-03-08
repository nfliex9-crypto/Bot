from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from app.core.config import settings
from app.execution.base import ExecutionEngine, OrderResult


class PaperExecutor(ExecutionEngine):
    """
    Paper trading executor — simulates order fills locally.
    Tracks virtual positions and balance in memory.
    """

    def __init__(self) -> None:
        self._balance = settings.account_balance
        self._positions: dict[str, dict] = {}
        self._order_history: list[dict] = []

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> OrderResult:
        order_id = str(uuid.uuid4())[:12]

        # In paper mode, filled_price == current mid-price (passed via the pipeline)
        # We simulate a fill at the entry_price the strategy calculated
        self._positions[symbol] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": 0.0,  # set by caller
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "opened_at": datetime.now(timezone.utc),
        }

        self._order_history.append(
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "type": "open",
                "timestamp": datetime.now(timezone.utc),
            }
        )

        logger.info(
            f"[PAPER] Order filled: {symbol} {side} qty={quantity} id={order_id}"
        )
        return OrderResult(
            success=True,
            order_id=order_id,
            filled_price=0.0,
            filled_qty=quantity,
        )

    async def close_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_id: str | None = None,
    ) -> OrderResult:
        pos = self._positions.pop(symbol, None)
        oid = order_id or (pos["order_id"] if pos else str(uuid.uuid4())[:12])

        self._order_history.append(
            {
                "order_id": oid,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "type": "close",
                "timestamp": datetime.now(timezone.utc),
            }
        )

        logger.info(f"[PAPER] Position closed: {symbol} qty={quantity}")
        return OrderResult(success=True, order_id=oid, filled_qty=quantity)

    async def modify_stop_loss(
        self,
        symbol: str,
        order_id: str,
        new_stop_loss: float,
    ) -> OrderResult:
        if symbol in self._positions:
            self._positions[symbol]["stop_loss"] = new_stop_loss
            logger.info(f"[PAPER] SL modified: {symbol} → {new_stop_loss}")
        return OrderResult(success=True, order_id=order_id)

    async def get_open_positions(self) -> list[dict]:
        return list(self._positions.values())

    async def get_account_balance(self) -> float:
        return self._balance

    def update_balance(self, pnl: float) -> None:
        self._balance += pnl
