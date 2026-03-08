from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class RiskProfile:
    account_balance: float
    risk_per_trade_pct: float
    max_drawdown_pct: float
    max_trades_per_session: int


class RiskManager:
    def __init__(self, profile: RiskProfile) -> None:
        self.profile = profile
        self.starting_balance = profile.account_balance
        self.current_balance = profile.account_balance
        self._session_trade_count: dict[str, int] = {}

    @property
    def drawdown_pct(self) -> float:
        if self.starting_balance <= 0:
            return 0.0
        return max(0.0, ((self.starting_balance - self.current_balance) / self.starting_balance) * 100)

    def can_open_trade(self, now: datetime) -> bool:
        session_key = now.strftime("%Y-%m-%d")
        session_count = self._session_trade_count.get(session_key, 0)
        if session_count >= self.profile.max_trades_per_session:
            return False
        if self.drawdown_pct >= self.profile.max_drawdown_pct:
            return False
        return True

    def mark_trade_opened(self, now: datetime) -> None:
        session_key = now.strftime("%Y-%m-%d")
        self._session_trade_count[session_key] = self._session_trade_count.get(session_key, 0) + 1

    def update_balance(self, pnl: float) -> None:
        self.current_balance += pnl

    def position_size(self, entry_price: float, stop_loss: float) -> float:
        risk_amount = self.profile.account_balance * (self.profile.risk_per_trade_pct / 100.0)
        stop_distance = abs(entry_price - stop_loss)
        if stop_distance <= 0:
            return 0.0
        return max(0.0, risk_amount / stop_distance)
