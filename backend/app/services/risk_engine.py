from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    quantity: float = 0.0


class RiskEngine:
    def __init__(self, risk_per_trade: float, max_drawdown: float, max_trades_per_session: int) -> None:
        self.risk_per_trade = risk_per_trade
        self.max_drawdown = max_drawdown
        self.max_trades_per_session = max_trades_per_session

    def calculate_drawdown(self, current_equity: float, peak_equity: float) -> float:
        if peak_equity <= 0:
            return 0.0
        return max(0.0, (peak_equity - current_equity) / peak_equity)

    def position_size(self, equity: float, entry: float, stop_loss: float) -> float:
        risk_amount = equity * self.risk_per_trade
        stop_distance = abs(entry - stop_loss)
        if stop_distance <= 0:
            return 0.0
        return max(0.0, risk_amount / stop_distance)

    def evaluate(
        self,
        equity: float,
        peak_equity: float,
        session_trade_count: int,
        entry: float,
        stop_loss: float,
    ) -> RiskDecision:
        if session_trade_count >= self.max_trades_per_session:
            return RiskDecision(False, "max trades per session reached")

        drawdown = self.calculate_drawdown(equity, peak_equity)
        if drawdown >= self.max_drawdown:
            return RiskDecision(False, "max drawdown guard triggered")

        qty = self.position_size(equity, entry, stop_loss)
        if qty <= 0:
            return RiskDecision(False, "invalid stop distance")

        return RiskDecision(True, "approved", quantity=qty)

    def move_stop_to_breakeven(self, entry_price: float) -> float:
        return entry_price
