from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Order:
    symbol: str
    side: str
    qty: float
    order_type: str = "MKT"
    limit_price: float | None = None


@dataclass
class Fill:
    order_id: str
    symbol: str
    qty: float
    price: float
    status: str


class BrokerInterface(ABC):
    @abstractmethod
    def place_order(self, order: Order) -> str:
        """Place an order and return broker order ID."""

    @abstractmethod
    def get_fill(self, order_id: str) -> Fill | None:
        """Fetch latest fill info for order id."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order if possible."""

    @abstractmethod
    def positions(self) -> dict[str, float]:
        """Current positions by symbol."""
