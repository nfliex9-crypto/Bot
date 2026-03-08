from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderRequest:
    market: str
    symbol: str
    side: str
    quantity: float
    price: float
    stop_loss: float


@dataclass
class OrderResult:
    success: bool
    execution_ref: Optional[str]
    filled_price: float
    message: str = ""


class BaseExecutor:
    def place_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    def close_partial(self, symbol: str, side: str, quantity: float) -> OrderResult:
        raise NotImplementedError

