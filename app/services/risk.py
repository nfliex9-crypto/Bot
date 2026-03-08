from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(slots=True)
class RiskCheckResult:
    allowed: bool
    reason: str | None = None


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_drawdown(self, equity: float, peak_equity: float) -> RiskCheckResult:
        if peak_equity <= 0:
            return RiskCheckResult(True)
        drawdown = max((peak_equity - equity) / peak_equity, 0.0)
        if drawdown >= self.settings.max_drawdown:
            return RiskCheckResult(False, "max_drawdown_reached")
        return RiskCheckResult(True)

    def validate_trade_limit(self, trades_this_session: int) -> RiskCheckResult:
        if trades_this_session >= self.settings.max_trades_per_session:
            return RiskCheckResult(False, "max_trades_per_session_reached")
        return RiskCheckResult(True)

    def risk_amount(self, equity: float) -> float:
        return round(equity * self.settings.risk_per_trade, 2)

    def position_size(self, equity: float, entry_price: float, stop_loss: float) -> float:
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        size = self.risk_amount(equity) / risk_per_unit
        return max(round(size, 6), 0.0)
