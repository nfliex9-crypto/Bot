"""Risk management: position sizing, drawdown, session limits."""
from config import settings


class RiskManager:
    """Enforces risk parameters."""

    def __init__(
        self,
        account_balance: float | None = None,
        risk_per_trade: float | None = None,
        max_drawdown: float | None = None,
        max_trades_per_session: int | None = None,
    ):
        self.account_balance = account_balance or settings.ACCOUNT_BALANCE
        self.risk_per_trade = risk_per_trade or settings.RISK_PER_TRADE
        self.max_drawdown = max_drawdown or settings.MAX_DRAWDOWN
        self.max_trades_per_session = max_trades_per_session or settings.MAX_TRADES_PER_SESSION
        self.session_trades = 0
        self.peak_balance = self.account_balance
        self.current_drawdown_pct = 0.0

    def reset_session(self):
        """Reset session trade count (call at session start)."""
        self.session_trades = 0

    def update_balance(self, new_balance: float):
        """Update account balance and track drawdown."""
        self.account_balance = new_balance
        if new_balance > self.peak_balance:
            self.peak_balance = new_balance
        self.current_drawdown_pct = (
            (self.peak_balance - new_balance) / self.peak_balance * 100
            if self.peak_balance > 0
            else 0
        )

    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed.
        Returns (allowed, reason).
        """
        if self.session_trades >= self.max_trades_per_session:
            return False, f"Max trades per session ({self.max_trades_per_session}) reached"
        if self.current_drawdown_pct >= self.max_drawdown:
            return False, f"Max drawdown ({self.max_drawdown}%) exceeded"
        return True, "OK"

    def position_size(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
        min_confidence: float = 0.6,
        confidence: float = 1.0,
    ) -> tuple[float, float]:
        """
        Calculate position size in units and risk amount.
        Returns (position_size_units, risk_amount).
        """
        risk_amount = self.account_balance * (self.risk_per_trade / 100)
        risk_amount *= confidence  # Scale by AI confidence

        if direction.lower() in ("long", "buy"):
            risk_per_unit = entry_price - stop_loss
        else:
            risk_per_unit = stop_loss - entry_price

        if risk_per_unit <= 0:
            return 0.0, 0.0

        if confidence < min_confidence:
            return 0.0, 0.0

        size = risk_amount / risk_per_unit
        return size, risk_amount

    def record_trade(self):
        """Record a trade for session limit."""
        self.session_trades += 1
