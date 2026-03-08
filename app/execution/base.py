from dataclasses import dataclass
from typing import Protocol


@dataclass
class OrderRequest:
    symbol: str
    market_type: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    confidence: float
    metadata: dict


@dataclass
class ExecutionResult:
    accepted: bool
    order_id: str
    message: str
    raw: dict


class BrokerExecutor(Protocol):
    def place_order(self, req: OrderRequest) -> ExecutionResult: ...

