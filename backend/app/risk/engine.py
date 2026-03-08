from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.config import get_settings
from app.schemas import RiskPlan, Signal
from app.strategy.signals import compute_atr

settings = get_settings()


@dataclass
class SessionState:
    start_equity: float
    current_equity: float
    trades_taken: int = 0

    @property
    def drawdown(self) -> float:
        if self.start_equity <= 0:
            return 0.0
        return max(0.0, (self.start_equity - self.current_equity) / self.start_equity)


class RiskEngine:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    def upsert_session(self, session_id: str, equity: float) -> SessionState:
        state = self.sessions.get(session_id)
        if state is None:
            state = SessionState(start_equity=equity, current_equity=equity)
            self.sessions[session_id] = state
        else:
            state.current_equity = equity
        return state

    def build_risk_plan(
        self,
        session_id: str,
        signal: Signal,
        df: pd.DataFrame,
        equity: float,
    ) -> RiskPlan:
        state = self.upsert_session(session_id=session_id, equity=equity)

        if signal.direction == "none":
            return RiskPlan(allowed=False, reason="no executable direction")
        if state.drawdown >= settings.max_drawdown:
            return RiskPlan(allowed=False, reason="max drawdown exceeded")
        if state.trades_taken >= settings.max_trades_per_session:
            return RiskPlan(allowed=False, reason="session trade limit reached")

        atr = compute_atr(df).iloc[-1]
        entry = float(df["close"].iloc[-1])
        stop_distance = float(atr * settings.atr_multiplier)

        if signal.direction == "buy":
            stop_loss = entry - stop_distance
            tp1 = entry + stop_distance * settings.tp_multipliers[0]
            tp2 = entry + stop_distance * settings.tp_multipliers[1]
            tp3 = entry + stop_distance * settings.tp_multipliers[2]
        else:
            stop_loss = entry + stop_distance
            tp1 = entry - stop_distance * settings.tp_multipliers[0]
            tp2 = entry - stop_distance * settings.tp_multipliers[1]
            tp3 = entry - stop_distance * settings.tp_multipliers[2]

        risk_amount = equity * settings.risk_per_trade
        position_size = risk_amount / stop_distance if stop_distance > 0 else 0.0
        if position_size <= 0:
            return RiskPlan(allowed=False, reason="invalid position size")

        return RiskPlan(
            allowed=True,
            reason="risk checks passed",
            position_size=round(position_size, 4),
            entry_price=entry,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
        )

    def register_trade(self, session_id: str) -> None:
        if session_id in self.sessions:
            self.sessions[session_id].trades_taken += 1
