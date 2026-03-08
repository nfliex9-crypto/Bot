from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import Settings


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.start_balance = settings.account_balance
        self.current_equity = settings.account_balance
        self.peak_equity = settings.account_balance
        self.trade_counter: dict[str, int] = {}

    def _session_key(self, now: datetime) -> str:
        return now.astimezone(timezone.utc).strftime("%Y-%m-%d")

    def can_open_trade(self, now: datetime | None = None) -> RiskDecision:
        now = now or datetime.now(timezone.utc)
        drawdown = self.drawdown_pct
        if drawdown >= self.settings.max_drawdown:
            return RiskDecision(False, f"Max drawdown reached ({drawdown:.2%})")

        key = self._session_key(now)
        trades = self.trade_counter.get(key, 0)
        if trades >= self.settings.max_trades_per_session:
            return RiskDecision(False, f"Session max trades reached ({trades})")
        return RiskDecision(True)

    @property
    def drawdown_pct(self) -> float:
        if self.start_balance <= 0:
            return 0.0
        peak = max(self.start_balance, self.peak_equity)
        return max(0.0, (peak - self.current_equity) / peak)

    @property
    def risk_amount(self) -> float:
        return self.current_equity * self.settings.risk_per_trade

    def compute_position_size(self, entry: float, stop_loss: float, market_type: str = "crypto") -> float:
        distance = abs(entry - stop_loss)
        if distance <= 0:
            return 0.0
        if market_type == "forex":
            contract_size = 100000.0
            lots = self.risk_amount / (distance * contract_size)
            return max(round(lots, 2), 0.01)
        qty = self.risk_amount / distance
        return max(round(qty, 6), 0.0)

    def register_open_trade(self, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        key = self._session_key(now)
        self.trade_counter[key] = self.trade_counter.get(key, 0) + 1

    def apply_realized_pnl(self, pnl: float) -> None:
        self.current_equity += pnl
        self.peak_equity = max(self.peak_equity, self.current_equity)

