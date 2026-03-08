from __future__ import annotations

import asyncio
from loguru import logger

from app.core.config import settings
from app.execution.base import ExecutionEngine, OrderResult

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
except ImportError:
    BinanceClient = None  # type: ignore[assignment, misc]
    BinanceAPIException = Exception  # type: ignore[assignment, misc]


class BinanceExecutor(ExecutionEngine):
    """Live execution via Binance spot API."""

    def __init__(self) -> None:
        self._client: BinanceClient | None = None

    async def connect(self) -> bool:
        if BinanceClient is None:
            return False
        try:
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                lambda: BinanceClient(
                    api_key=settings.binance_api_key,
                    api_secret=settings.binance_api_secret,
                    testnet=settings.binance_testnet,
                ),
            )
            return True
        except Exception as exc:
            logger.error(f"Binance executor connect failed: {exc}")
            return False

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> OrderResult:
        if self._client is None:
            return OrderResult(success=False, error="Binance client not connected")

        loop = asyncio.get_event_loop()
        bn_side = "BUY" if side == "long" else "SELL"

        try:
            order = await loop.run_in_executor(
                None,
                lambda: self._client.create_order(
                    symbol=symbol,
                    side=bn_side,
                    type="MARKET",
                    quantity=f"{quantity:.6f}",
                ),
            )

            filled_price = float(order.get("fills", [{}])[0].get("price", 0))
            filled_qty = float(order.get("executedQty", 0))

            logger.info(
                f"Binance order filled: {symbol} {side} {filled_qty} @ {filled_price} "
                f"id={order['orderId']}"
            )

            # Place OCO stop-loss if provided
            if stop_loss and take_profit:
                await self._place_oco(symbol, side, quantity, stop_loss, take_profit)

            return OrderResult(
                success=True,
                order_id=str(order["orderId"]),
                filled_price=filled_price,
                filled_qty=filled_qty,
            )

        except BinanceAPIException as exc:
            return OrderResult(success=False, error=str(exc))

    async def _place_oco(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float,
        take_profit: float,
    ) -> None:
        if self._client is None:
            return

        loop = asyncio.get_event_loop()
        oco_side = "SELL" if side == "long" else "BUY"

        try:
            await loop.run_in_executor(
                None,
                lambda: self._client.create_oco_order(
                    symbol=symbol,
                    side=oco_side,
                    quantity=f"{quantity:.6f}",
                    price=f"{take_profit:.2f}",
                    stopPrice=f"{stop_loss:.2f}",
                    stopLimitPrice=f"{stop_loss:.2f}",
                    stopLimitTimeInForce="GTC",
                ),
            )
            logger.info(f"Binance OCO placed: {symbol} SL={stop_loss} TP={take_profit}")
        except Exception as exc:
            logger.error(f"Binance OCO failed: {exc}")

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
        logger.info(
            f"Binance SL modify requested for {symbol} — "
            f"OCO replacement would be needed (not atomic on spot)"
        )
        return OrderResult(success=True, order_id=order_id)

    async def get_open_positions(self) -> list[dict]:
        if self._client is None:
            return []
        loop = asyncio.get_event_loop()
        try:
            account = await loop.run_in_executor(
                None, self._client.get_account
            )
            positions = []
            for balance in account.get("balances", []):
                free = float(balance["free"])
                locked = float(balance["locked"])
                if free + locked > 0 and balance["asset"] not in ("USDT", "BUSD", "USD"):
                    positions.append(
                        {
                            "symbol": balance["asset"] + "USDT",
                            "quantity": free + locked,
                            "free": free,
                            "locked": locked,
                        }
                    )
            return positions
        except Exception:
            return []

    async def get_account_balance(self) -> float:
        if self._client is None:
            return 0.0
        loop = asyncio.get_event_loop()
        try:
            account = await loop.run_in_executor(
                None, self._client.get_account
            )
            for balance in account.get("balances", []):
                if balance["asset"] == "USDT":
                    return float(balance["free"]) + float(balance["locked"])
            return 0.0
        except Exception:
            return 0.0
