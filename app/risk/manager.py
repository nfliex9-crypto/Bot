from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AccountSnapshot, Trade


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.start_balance = settings.account_balance

    def compute_position_size(self, entry: float, stop: float) -> float:
        risk_amount = self.settings.account_balance * self.settings.risk_per_trade
        distance = abs(entry - stop)
        if distance <= 0:
            return 0.0
        qty = risk_amount / distance
        return max(qty, 0.0)

    def can_trade(self, session: Session) -> tuple[bool, str]:
        now = datetime.now(UTC)
        day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        day_end = datetime(now.year, now.month, now.day, 23, 59, 59, tzinfo=UTC)

        trades_today = session.scalar(
            select(func.count(Trade.id)).where(Trade.created_at >= day_start, Trade.created_at <= day_end)
        )
        if trades_today is None:
            trades_today = 0
        if trades_today >= self.settings.max_trades_per_session:
            return False, "Max trades per session reached."

        latest_snapshot = session.execute(
            select(AccountSnapshot).order_by(AccountSnapshot.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        equity = latest_snapshot.equity if latest_snapshot else self.settings.account_balance
        drawdown = max(0.0, (self.start_balance - equity) / self.start_balance)
        if drawdown >= self.settings.max_drawdown:
            return False, "Max drawdown reached."
        return True, "Risk checks passed."

