from __future__ import annotations

from app.core.config import Settings
from app.domain.models import MarketSnapshot, StopMethod, TradeDirection, TradeSetup
from app.services.indicators import (
    atr,
    break_of_structure,
    liquidity_sweep,
    pullback_ready,
    recent_range,
    structure_bias,
)


class LiquiditySweepBosPullbackStrategy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_setup(self, snapshot: MarketSnapshot) -> TradeSetup | None:
        bias, bias_score = structure_bias(snapshot.h1)
        bos_direction, bos_strength = break_of_structure(snapshot.m15)
        sweep_direction, sweep_strength, structure_level = liquidity_sweep(snapshot.m5)

        if "neutral" in {bias, bos_direction, sweep_direction}:
            return None
        if not (bias == bos_direction == sweep_direction):
            return None

        pullback_ok, pullback_level = pullback_ready(snapshot.m5, sweep_direction)
        if not pullback_ok:
            return None

        current_price = snapshot.current_price
        atr_value = float(atr(snapshot.m5, self.settings.atr_period).iloc[-1])
        if atr_value <= 0:
            return None

        direction = TradeDirection.LONG if bias == "bullish" else TradeDirection.SHORT
        risk_score = min(max((bias_score + bos_strength + sweep_strength) / 3.0, 0.0), 1.0)
        entry_price = current_price

        if self.settings.stop_method == StopMethod.STRUCTURE:
            stop_loss = self._structure_stop(direction, entry_price, structure_level, atr_value)
        else:
            stop_loss = self._atr_stop(direction, entry_price, atr_value)

        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return None

        tp1, tp2, tp3 = self._targets(direction, entry_price, risk_per_unit)
        rationale = [
            f"H1 bias aligned {bias}",
            f"M15 break of structure confirmed {bos_direction}",
            f"M5 liquidity sweep strength {sweep_strength:.2f}",
            f"Pullback entry near {pullback_level:.5f}",
        ]

        metadata = {
            "bias_score": round(bias_score, 4),
            "bos_strength": round(float(bos_strength), 4),
            "sweep_strength": round(float(sweep_strength), 4),
            "pullback_level": round(float(pullback_level), 8),
            "h1_range": round(recent_range(snapshot.h1), 8),
            "m15_range": round(recent_range(snapshot.m15), 8),
            "m5_range": round(recent_range(snapshot.m5), 8),
        }

        return TradeSetup(
            market=snapshot.market,
            symbol=snapshot.symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            risk_per_unit=risk_per_unit,
            strategy_score=round(risk_score, 4),
            rationale=rationale,
            session_label="unknown",
            structure_level=structure_level,
            atr_value=atr_value,
            metadata=metadata,
        )

    def _atr_stop(self, direction: TradeDirection, entry_price: float, atr_value: float) -> float:
        offset = atr_value * self.settings.atr_multiplier
        if direction == TradeDirection.LONG:
            return entry_price - offset
        return entry_price + offset

    def _structure_stop(
        self,
        direction: TradeDirection,
        entry_price: float,
        structure_level: float,
        atr_value: float,
    ) -> float:
        buffer = atr_value * self.settings.structure_buffer_atr
        if direction == TradeDirection.LONG:
            candidate = structure_level - buffer
            return min(candidate, entry_price - buffer)
        candidate = structure_level + buffer
        return max(candidate, entry_price + buffer)

    @staticmethod
    def _targets(direction: TradeDirection, entry: float, risk: float) -> tuple[float, float, float]:
        if direction == TradeDirection.LONG:
            return entry + risk, entry + risk * 1.5, entry + risk * 2.0
        return entry - risk, entry - risk * 1.5, entry - risk * 2.0
