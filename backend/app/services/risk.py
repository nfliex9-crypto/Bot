from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.db.models import OrderSide, Trade
from app.services.strategy import StrategySignal

settings = get_settings()


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    quantity: float = 0.0
    risk_amount: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    session_name: str = ""


class RiskEngine:
    def evaluate(
        self,
        signal: StrategySignal,
        account_equity: float,
        current_drawdown: float,
        session_trade_count: int,
    ) -> RiskDecision:
        session_name = self.current_session_name()

        if current_drawdown >= settings.max_drawdown:
            return RiskDecision(False, "Max drawdown limit reached.", session_name=session_name)

        if session_trade_count >= settings.max_trades_per_session:
            return RiskDecision(False, "Maximum trades for the current session reached.", session_name=session_name)

        stop_distance = abs(signal.entry_price - signal.stop_loss)
        if stop_distance <= 0:
            return RiskDecision(False, "Invalid stop distance.", session_name=session_name)

        risk_amount = account_equity * settings.risk_per_trade
        quantity = risk_amount / stop_distance

        return RiskDecision(
            approved=True,
            reason="Trade approved by risk engine.",
            quantity=round(quantity, 6),
            risk_amount=round(risk_amount, 2),
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            session_name=session_name,
        )

    def mark_break_even(self, trade: Trade, current_price: float) -> bool:
        if trade.break_even_armed:
            return False

        if trade.side == OrderSide.LONG and current_price >= trade.tp1:
            trade.stop_loss = trade.entry_price
            trade.break_even_armed = True
            trade.highest_tp_hit = max(trade.highest_tp_hit, 1)
            return True

        if trade.side == OrderSide.SHORT and current_price <= trade.tp1:
            trade.stop_loss = trade.entry_price
            trade.break_even_armed = True
            trade.highest_tp_hit = max(trade.highest_tp_hit, 1)
            return True

        return False

    @staticmethod
    def current_session_name(now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        hour = now.hour
        if 0 <= hour < 8:
            return "Asia"
        if 8 <= hour < 16:
            return "London"
        return "NewYork"

    @staticmethod
    def current_session_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
        now = now or datetime.now(UTC)
        session = RiskEngine.current_session_name(now)
        if session == "Asia":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif session == "London":
            start = now.replace(hour=8, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(hour=16, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=8)
        return start, end
