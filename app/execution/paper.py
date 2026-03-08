from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, date, datetime
from uuid import uuid4

from app.core.config import Settings
from app.domain.models import AccountSnapshot, MarketType, OpenTrade, SizedTradeSignal
from app.execution.base import BrokerOrderResult


class PaperBroker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._snapshots = {
            MarketType.FOREX: AccountSnapshot(
                balance=settings.initial_account_balance,
                equity=settings.initial_account_balance,
                peak_balance=settings.initial_account_balance,
                session_trade_count=0,
            ),
            MarketType.CRYPTO: AccountSnapshot(
                balance=settings.initial_account_balance,
                equity=settings.initial_account_balance,
                peak_balance=settings.initial_account_balance,
                session_trade_count=0,
            ),
        }
        self._session_date = datetime.now(UTC).date()

    async def get_account_snapshot(self, market: MarketType) -> AccountSnapshot:
        self._reset_session_if_needed()
        return deepcopy(self._snapshots[market])

    async def place_trade(self, signal: SizedTradeSignal) -> BrokerOrderResult:
        self._reset_session_if_needed()
        snapshot = self._snapshots[signal.market]
        snapshot.session_trade_count += 1
        return BrokerOrderResult(
            broker_trade_id=f"paper-{uuid4().hex[:12]}",
            fill_price=signal.entry,
            filled_size=signal.position_size,
            status="filled",
        )

    async def move_stop_to_break_even(self, trade: OpenTrade) -> None:
        return None

    async def close_partial(self, trade: OpenTrade, quantity: float, reason: str) -> None:
        return None

    async def close_trade(self, trade: OpenTrade, reason: str) -> None:
        return None

    async def book_realized_pnl(self, market: MarketType, pnl: float) -> None:
        snapshot = self._snapshots[market]
        snapshot.balance += pnl
        snapshot.equity = snapshot.balance
        snapshot.peak_balance = max(snapshot.peak_balance, snapshot.balance)

    def _reset_session_if_needed(self) -> None:
        current = datetime.now(UTC).date()
        if current == self._session_date:
            return
        self._session_date = current
        for snapshot in self._snapshots.values():
            snapshot.session_trade_count = 0
