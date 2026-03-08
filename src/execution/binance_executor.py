"""
Binance trade execution engine.
Handles paper (simulated) and live order placement via Binance API.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from loguru import logger

from src.execution.base_executor import BaseExecutor, OrderResult, CloseResult
from config.settings import settings

try:
    from binance import AsyncClient
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    AsyncClient = None
    BinanceAPIException = Exception
    BINANCE_AVAILABLE = False

_PAPER_POSITIONS: dict = {}


class BinanceExecutor(BaseExecutor):
    """
    Executes trades on Binance spot/futures.
    Paper mode: tracks simulated positions in memory.
    Live mode: submits real orders via Binance API.
    """

    def __init__(self, paper_mode: bool = True):
        super().__init__("Binance", paper_mode=paper_mode)
        self._client: Optional[object] = None

    async def initialize(self) -> None:
        if not self.paper_mode and BINANCE_AVAILABLE:
            self._client = await AsyncClient.create(
                api_key=settings.binance_api_key,
                api_secret=settings.binance_secret_key,
                testnet=settings.binance_testnet,
            )

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
        return await self._live_open(symbol, direction, lot_size, entry_price, stop_loss, tp1)

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
                return True
            return False

        # For live: cancel old stop order and place new one
        if not BINANCE_AVAILABLE or not self._client:
            return False

        try:
            # Cancel existing stop orders for this position
            open_orders = await self._client.get_open_orders(symbol=symbol)
            for order in open_orders:
                if order.get("type") in ("STOP_LOSS", "STOP_LOSS_LIMIT"):
                    await self._client.cancel_order(symbol=symbol, orderId=order["orderId"])

            # Place new stop loss
            pos = _PAPER_POSITIONS.get(broker_ticket, {})
            qty = pos.get("lot_size", lot_size)
            side = "SELL" if pos.get("direction") == "long" else "BUY"
            await self._client.create_order(
                symbol=symbol,
                side=side,
                type="STOP_LOSS_LIMIT",
                quantity=qty,
                stopPrice=new_stop_loss,
                price=new_stop_loss,
                timeInForce="GTC",
            )
            return True
        except BinanceAPIException as e:
            logger.error(f"Binance modify SL error: {e}")
            return False

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

        if not BINANCE_AVAILABLE or not self._client:
            return []

        try:
            account = await self._client.get_account()
            positions = []
            for asset in account.get("balances", []):
                free = float(asset["free"])
                locked = float(asset["locked"])
                if free + locked > 0.0001 and asset["asset"] != "USDT":
                    positions.append({
                        "symbol": asset["asset"] + "USDT",
                        "lot_size": free + locked,
                        "direction": "long",
                    })
            return positions
        except BinanceAPIException as e:
            logger.error(f"Binance get positions error: {e}")
            return []

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
            f"[PAPER/CRYPTO] TRADE OPEN | {symbol} {direction.upper()} | "
            f"qty={lot_size} entry={price} sl={stop_loss} tp1={tp1} ticket={ticket}"
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
        qty = pos["lot_size"]

        if direction == "long":
            pnl = (close - pos["entry_price"]) * qty
        else:
            pnl = (pos["entry_price"] - close) * qty

        pnl = round(pnl, 4)
        logger.info(
            f"[PAPER/CRYPTO] TRADE CLOSE | {symbol} | "
            f"close={close} pnl={pnl} ticket={broker_ticket}"
        )
        return CloseResult(success=True, close_price=close, pnl=pnl, commission=0.0, error=None)

    # ── Live Trading ──────────────────────────────────────────────────────────

    async def _live_open(
        self, symbol: str, direction: str, lot_size: float,
        entry_price: Optional[float], stop_loss: float, tp1: float
    ) -> OrderResult:
        if not BINANCE_AVAILABLE or not self._client:
            return OrderResult(success=False, broker_ticket=None, executed_price=None,
                               executed_qty=None, commission=0.0, swap=0.0,
                               error="Binance client not initialized")

        try:
            side = "BUY" if direction == "long" else "SELL"
            order = await self._client.create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=lot_size,
            )
            # Place stop loss order
            stop_side = "SELL" if direction == "long" else "BUY"
            await self._client.create_order(
                symbol=symbol,
                side=stop_side,
                type="STOP_LOSS_LIMIT",
                quantity=lot_size,
                stopPrice=stop_loss,
                price=stop_loss,
                timeInForce="GTC",
            )
            # Place TP order
            await self._client.create_order(
                symbol=symbol,
                side=stop_side,
                type="LIMIT",
                quantity=lot_size,
                price=tp1,
                timeInForce="GTC",
            )
            executed_price = float(order.get("fills", [{}])[0].get("price", 0))
            logger.info(
                f"[LIVE/CRYPTO] TRADE OPEN | {symbol} {direction.upper()} | "
                f"qty={lot_size} price={executed_price} ticket={order['orderId']}"
            )
            return OrderResult(
                success=True,
                broker_ticket=str(order["orderId"]),
                executed_price=executed_price,
                executed_qty=float(order["executedQty"]),
                commission=0.0,
                swap=0.0,
                error=None,
            )
        except BinanceAPIException as e:
            logger.error(f"Binance live open error: {e}")
            return OrderResult(success=False, broker_ticket=None, executed_price=None,
                               executed_qty=None, commission=0.0, swap=0.0, error=str(e))

    async def _live_close(
        self, broker_ticket: str, symbol: str, lot_size: float,
        direction: str, close_price: Optional[float]
    ) -> CloseResult:
        if not BINANCE_AVAILABLE or not self._client:
            return CloseResult(success=False, close_price=None, pnl=None,
                               commission=0.0, error="Binance client not initialized")

        try:
            side = "SELL" if direction == "long" else "BUY"
            order = await self._client.create_order(
                symbol=symbol, side=side, type="MARKET", quantity=lot_size
            )
            executed_price = float(order.get("fills", [{}])[0].get("price", 0))
            logger.info(f"[LIVE/CRYPTO] TRADE CLOSE | {symbol} ticket={broker_ticket}")
            return CloseResult(success=True, close_price=executed_price, pnl=None,
                               commission=0.0, error=None)
        except BinanceAPIException as e:
            logger.error(f"Binance live close error: {e}")
            return CloseResult(success=False, close_price=None, pnl=None,
                               commission=0.0, error=str(e))
