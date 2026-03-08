from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import AccountSnapshot, MarketType, OpenTrade, SizedTradeSignal


@dataclass(slots=True)
class BrokerOrderResult:
    broker_trade_id: str
    fill_price: float
    filled_size: float
    status: str


class Broker(Protocol):
    async def get_account_snapshot(self, market: MarketType) -> AccountSnapshot:
        ...

    async def place_trade(self, signal: SizedTradeSignal) -> BrokerOrderResult:
        ...

    async def move_stop_to_break_even(self, trade: OpenTrade) -> None:
        ...

    async def close_partial(self, trade: OpenTrade, quantity: float, reason: str) -> None:
        ...

    async def close_trade(self, trade: OpenTrade, reason: str) -> None:
        ...

    async def book_realized_pnl(self, market: MarketType, pnl: float) -> None:
        ...
