"""
Order Management System (OMS).

Tracks order lifecycle from creation through execution,
manages order queues, and provides fill reconciliation.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    TWAP = "twap"
    VWAP = "vwap"


@dataclass
class Order:
    """Represents a single order in the OMS."""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    strategy_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    created_at: float = field(default_factory=time.time)
    submitted_at: float = 0.0
    filled_at: float = 0.0
    latency_ms: float = 0.0
    broker_order_id: str = ""
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)

    @property
    def fill_pct(self) -> float:
        return self.filled_quantity / self.quantity if self.quantity > 0 else 0

    @property
    def notional(self) -> float:
        return self.filled_quantity * self.avg_fill_price

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "commission": self.commission,
            "slippage": self.slippage,
            "latency_ms": self.latency_ms,
        }


class OrderManager:
    """
    Manages the full order lifecycle.

    Maintains an order book, processes fills, and provides
    real-time position tracking.
    """

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, float] = {}
        self._fill_history: list[dict] = []

    def create_order(
        self,
        strategy_id: str,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
    ) -> Order:
        order = Order(
            strategy_id=strategy_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=abs(quantity),
            limit_price=limit_price,
        )
        self._orders[order.order_id] = order
        logger.info("Order created: %s %s %.2f %s", order.order_id, symbol, quantity, side.value)
        return order

    def submit_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or order.status != OrderStatus.PENDING:
            return False
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = time.time()
        return True

    def fill_order(
        self,
        order_id: str,
        filled_qty: float,
        fill_price: float,
        commission: float = 0.0,
    ) -> bool:
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False

        order.filled_quantity += filled_qty
        total_cost = order.avg_fill_price * (order.filled_quantity - filled_qty) + fill_price * filled_qty
        order.avg_fill_price = total_cost / order.filled_quantity if order.filled_quantity > 0 else 0
        order.commission += commission
        order.filled_at = time.time()
        order.latency_ms = (order.filled_at - order.submitted_at) * 1000 if order.submitted_at > 0 else 0

        if order.filled_quantity >= order.quantity * 0.999:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

        multiplier = 1.0 if order.side == OrderSide.BUY else -1.0
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + filled_qty * multiplier

        self._fill_history.append({
            "order_id": order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "quantity": filled_qty,
            "price": fill_price,
            "commission": commission,
            "timestamp": time.time(),
        })

        logger.info("Order filled: %s %s %.2f @ %.4f", order_id, order.symbol, filled_qty, fill_price)
        return True

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None or not order.is_active:
            return False
        order.status = OrderStatus.CANCELLED
        return True

    def get_position(self, symbol: str) -> float:
        return self._positions.get(symbol, 0.0)

    @property
    def positions(self) -> dict[str, float]:
        return dict(self._positions)

    @property
    def active_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.is_active]

    @property
    def fill_history(self) -> list[dict]:
        return list(self._fill_history)

    def generate_rebalance_orders(
        self,
        target_positions: dict[str, float],
        strategy_id: str = "",
    ) -> list[Order]:
        """Generate orders to move from current positions to target positions."""
        orders = []
        for symbol, target_qty in target_positions.items():
            current = self.get_position(symbol)
            delta = target_qty - current

            if abs(delta) < 1e-6:
                continue

            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            order = self.create_order(
                strategy_id=strategy_id,
                symbol=symbol,
                side=side,
                quantity=abs(delta),
            )
            orders.append(order)

        return orders
