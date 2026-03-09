from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .broker_interface import BrokerInterface, Order


@dataclass
class OrderIntent:
    strategy_id: str
    symbol: str
    target_qty: float


class OMS:
    def __init__(self, broker: BrokerInterface) -> None:
        self.broker = broker

    def submit_intent(self, intent: OrderIntent) -> str:
        side = "BUY" if intent.target_qty >= 0 else "SELL"
        order = Order(symbol=intent.symbol, side=side, qty=abs(intent.target_qty))
        return self.broker.place_order(order)

    @staticmethod
    def now_utc() -> str:
        return datetime.now(timezone.utc).isoformat()
