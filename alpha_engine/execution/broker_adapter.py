"""
Broker adapter interface and paper trading implementation.

Provides a unified interface for order submission across different
brokers, with a full-featured paper trading simulator for testing.
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .order_manager import Order, OrderSide, OrderStatus

logger = logging.getLogger(__name__)


@dataclass
class BrokerFill:
    """Fill report from broker."""
    order_id: str
    broker_order_id: str
    filled_quantity: float
    fill_price: float
    commission: float
    timestamp: float
    latency_ms: float


class BrokerAdapter(abc.ABC):
    """Abstract broker connection interface."""

    @abc.abstractmethod
    def connect(self) -> bool:
        ...

    @abc.abstractmethod
    def disconnect(self) -> None:
        ...

    @abc.abstractmethod
    def submit_order(self, order: Order) -> Optional[BrokerFill]:
        ...

    @abc.abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool:
        ...

    @abc.abstractmethod
    def get_account_value(self) -> float:
        ...

    @abc.abstractmethod
    def get_positions(self) -> dict[str, float]:
        ...

    @abc.abstractmethod
    def is_connected(self) -> bool:
        ...


class PaperBroker(BrokerAdapter):
    """
    Paper trading broker for simulation and testing.

    Simulates realistic fills with configurable slippage and latency.
    """

    def __init__(
        self,
        initial_capital: float = 10_000_000.0,
        commission_per_share: float = 0.005,
        slippage_bps: float = 1.0,
        fill_probability: float = 0.98,
        latency_ms: float = 10.0,
        seed: int = 42,
    ) -> None:
        self._capital = initial_capital
        self._cash = initial_capital
        self._commission = commission_per_share
        self._slippage_bps = slippage_bps
        self._fill_prob = fill_probability
        self._latency_ms = latency_ms
        self._rng = np.random.RandomState(seed)
        self._positions: dict[str, float] = {}
        self._prices: dict[str, float] = {}
        self._connected = False
        self._order_count = 0

    def connect(self) -> bool:
        self._connected = True
        logger.info("Paper broker connected (capital: $%.2f)", self._capital)
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper broker disconnected")

    def set_prices(self, prices: dict[str, float]) -> None:
        """Update current market prices for simulation."""
        self._prices.update(prices)

    def submit_order(self, order: Order) -> Optional[BrokerFill]:
        if not self._connected:
            logger.error("Broker not connected")
            return None

        self._order_count += 1
        broker_id = f"PAPER-{self._order_count:06d}"

        latency = max(1, self._rng.exponential(self._latency_ms))
        time.sleep(latency / 10000)

        if self._rng.random() > self._fill_prob:
            order.status = OrderStatus.REJECTED
            order.notes = "Simulated rejection"
            logger.warning("Order rejected (simulated): %s", order.order_id)
            return None

        base_price = self._prices.get(order.symbol, 100.0)
        slip_direction = 1 if order.side == OrderSide.BUY else -1
        slippage = self._slippage_bps / 10_000 * self._rng.uniform(0.5, 1.5)
        fill_price = base_price * (1 + slip_direction * slippage)

        fill_qty = order.quantity
        commission = fill_qty * self._commission

        notional = fill_qty * fill_price
        if order.side == OrderSide.BUY:
            if notional + commission > self._cash:
                fill_qty = (self._cash - commission) / fill_price
                notional = fill_qty * fill_price
            self._cash -= notional + commission
            self._positions[order.symbol] = self._positions.get(order.symbol, 0) + fill_qty
        else:
            self._cash += notional - commission
            self._positions[order.symbol] = self._positions.get(order.symbol, 0) - fill_qty

        fill = BrokerFill(
            order_id=order.order_id,
            broker_order_id=broker_id,
            filled_quantity=fill_qty,
            fill_price=fill_price,
            commission=commission,
            timestamp=time.time(),
            latency_ms=latency,
        )

        logger.debug(
            "Paper fill: %s %s %.2f @ %.4f (%.1fms)",
            order.symbol, order.side.value, fill_qty, fill_price, latency,
        )
        return fill

    def cancel_order(self, broker_order_id: str) -> bool:
        return True

    def get_account_value(self) -> float:
        position_value = sum(
            qty * self._prices.get(sym, 0) for sym, qty in self._positions.items()
        )
        return self._cash + position_value

    def get_positions(self) -> dict[str, float]:
        return dict(self._positions)

    def is_connected(self) -> bool:
        return self._connected
