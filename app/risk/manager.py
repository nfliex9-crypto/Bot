from __future__ import annotations

from dataclasses import dataclass
from math import floor

from app.core.config import Settings
from app.domain.models import AccountSnapshot, SizedTradeSignal, SymbolSpec, TradeSignal


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason: str = ""


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def can_open_trade(self, account: AccountSnapshot) -> RiskDecision:
        floor_equity = account.peak_balance * (1 - self.settings.max_drawdown)
        if account.equity <= floor_equity:
            return RiskDecision(False, "Max drawdown reached")
        if account.session_trade_count >= self.settings.max_trades_per_session:
            return RiskDecision(False, "Max trades for session reached")
        return RiskDecision(True, "")

    def size_trade(
        self,
        signal: TradeSignal,
        account: AccountSnapshot,
        spec: SymbolSpec,
    ) -> SizedTradeSignal:
        risk_amount = account.balance * self.settings.risk_per_trade
        stop_distance = signal.risk_per_unit
        if stop_distance <= 0:
            raise ValueError("Stop distance must be positive")

        ticks = stop_distance / max(spec.tick_size, 1e-12)
        loss_per_unit = ticks * spec.tick_value
        raw_qty = risk_amount / max(loss_per_unit, 1e-12)
        clipped_qty = min(raw_qty, spec.max_qty) if spec.max_qty else raw_qty
        rounded_qty = self._round_step(max(clipped_qty, spec.min_qty), spec.qty_step)
        if rounded_qty < spec.min_qty:
            rounded_qty = spec.min_qty

        return SizedTradeSignal(
            symbol=signal.symbol,
            market=signal.market,
            side=signal.side,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            take_profit_3=signal.take_profit_3,
            confidence=signal.confidence,
            stop_method=signal.stop_method,
            generated_at=signal.generated_at,
            metadata=signal.metadata,
            position_size=rounded_qty,
            risk_amount=risk_amount,
        )

    @staticmethod
    def _round_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        return round(floor(value / step) * step, 8)
