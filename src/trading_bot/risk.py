from __future__ import annotations

from dataclasses import dataclass
from math import floor

from .config import Settings, StopMethod
from .domain import InstrumentSpec, PositionPlan, TradeDirection, TradeSignal


@dataclass(slots=True)
class RiskCheck:
    allowed: bool
    reason: str = ""


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def daily_drawdown(self, realized_pnl_values: list[float]) -> float:
        losses = sum(pnl for pnl in realized_pnl_values if pnl < 0)
        return abs(losses)

    def can_open_trade(
        self,
        *,
        session_trade_count: int,
        open_positions: int,
        realized_pnls: list[float],
    ) -> RiskCheck:
        if session_trade_count >= self.settings.max_trades_per_session:
            return RiskCheck(False, "max trades per session reached")
        if open_positions >= self.settings.max_concurrent_trades:
            return RiskCheck(False, "max concurrent trades reached")
        if self.daily_drawdown(realized_pnls) >= self.settings.max_drawdown_amount:
            return RiskCheck(False, "max drawdown reached")
        return RiskCheck(True)

    def _select_stop(self, signal: TradeSignal) -> float:
        if self.settings.stop_method == StopMethod.STRUCTURE:
            return signal.stop_loss
        if signal.direction == TradeDirection.LONG:
            return signal.entry_price - (signal.atr * 1.5)
        return signal.entry_price + (signal.atr * 1.5)

    @staticmethod
    def quantize_quantity(quantity: float, step: float, min_quantity: float) -> float:
        if quantity < min_quantity:
            return 0.0
        rounded = floor(quantity / step) * step
        return round(max(rounded, min_quantity), 8)

    def build_position_plan(
        self,
        signal: TradeSignal,
        spec: InstrumentSpec,
    ) -> PositionPlan:
        stop = self._select_stop(signal)
        risk_distance = abs(signal.entry_price - stop)
        if risk_distance <= 0:
            raise ValueError("Risk distance must be positive")

        raw_quantity = self.settings.risk_amount / (risk_distance * spec.point_value)
        quantity = self.quantize_quantity(raw_quantity, spec.quantity_step, spec.min_quantity)
        if quantity <= 0:
            raise ValueError("Calculated quantity is below instrument minimum")

        take_profits = [
            signal.entry_price + (risk_distance * multiple)
            if signal.direction == TradeDirection.LONG
            else signal.entry_price - (risk_distance * multiple)
            for multiple in (1.0, 1.5, 2.0)
        ]
        return PositionPlan(
            symbol=signal.symbol,
            market=signal.market,
            direction=signal.direction,
            entry_price=signal.entry_price,
            stop_loss=stop,
            take_profit_levels=take_profits,
            quantity=quantity,
            risk_amount=self.settings.risk_amount,
            confidence=signal.confidence,
            session=signal.session,
            metadata={
                "features": signal.features,
                "atr": signal.atr,
                "bos_level": signal.bos_level,
                "liquidity_level": signal.liquidity_level,
                "pullback_level": signal.pullback_level,
                "reason": signal.reason,
            },
        )
