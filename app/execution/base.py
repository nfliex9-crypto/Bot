from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderResult:
    success: bool
    order_id: str = ""
    filled_price: float = 0.0
    filled_qty: float = 0.0
    error: str = ""


class ExecutionEngine(abc.ABC):

    @abc.abstractmethod
    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> OrderResult:
        ...

    @abc.abstractmethod
    async def close_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_id: str | None = None,
    ) -> OrderResult:
        ...

    @abc.abstractmethod
    async def modify_stop_loss(
        self,
        symbol: str,
        order_id: str,
        new_stop_loss: float,
    ) -> OrderResult:
        ...

    @abc.abstractmethod
    async def get_open_positions(self) -> list[dict]:
        ...

    @abc.abstractmethod
    async def get_account_balance(self) -> float:
        ...
