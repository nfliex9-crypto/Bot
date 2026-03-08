from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


MarketType = Literal["forex", "crypto"]
OrderSide = Literal["buy", "sell"]


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    market: MarketType
    side: OrderSide
    quantity: float
    entry_price: float
    stop_loss: float
    take_profits: list[float]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionResult:
    broker_order_id: str
    submitted_at: datetime
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerExecutor(ABC):
    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    async def close_position(self, symbol: str, market: MarketType) -> None:
        raise NotImplementedError
