from __future__ import annotations

import uuid

from .broker_interface import BrokerInterface, Fill, Order


class PaperBroker(BrokerInterface):
    def __init__(self) -> None:
        self._fills: dict[str, Fill] = {}
        self._positions: dict[str, float] = {}

    def place_order(self, order: Order) -> str:
        order_id = str(uuid.uuid4())
        signed_qty = order.qty if order.side.upper() == "BUY" else -order.qty
        self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + signed_qty
        self._fills[order_id] = Fill(order_id=order_id, symbol=order.symbol, qty=order.qty, price=0.0, status="FILLED")
        return order_id

    def get_fill(self, order_id: str) -> Fill | None:
        return self._fills.get(order_id)

    def cancel_order(self, order_id: str) -> bool:
        return order_id in self._fills

    def positions(self) -> dict[str, float]:
        return dict(self._positions)
