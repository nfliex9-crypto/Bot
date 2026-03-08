from __future__ import annotations

import logging
from typing import Dict

from ai.model import TradingAIModel
from config.settings import settings
from core.models import TradeSignal

logger = logging.getLogger(__name__)


class ConfidenceScorer:
    """Combines AI model output with rule-based adjustments."""

    def __init__(self, model: TradingAIModel) -> None:
        self._model = model

    def score(self, signal: TradeSignal) -> float:
        base_confidence = self._model.predict_confidence(signal.features)
        adjustments = self._rule_adjustments(signal)
        final = max(0.0, min(1.0, base_confidence + adjustments))

        logger.debug(
            "%s %s confidence: base=%.3f adj=%.3f final=%.3f",
            signal.symbol, signal.signal_type.value,
            base_confidence, adjustments, final,
        )
        return final

    def meets_threshold(self, confidence: float) -> bool:
        return confidence >= settings.ai_min_confidence

    @staticmethod
    def _rule_adjustments(signal: TradeSignal) -> float:
        adj = 0.0

        if signal.risk_reward >= 2.0:
            adj += 0.05
        elif signal.risk_reward < 1.2:
            adj -= 0.10

        from core.enums import SignalType
        if signal.signal_type == SignalType.PULLBACK_ENTRY:
            adj += 0.05
        elif signal.signal_type == SignalType.LIQUIDITY_SWEEP:
            adj += 0.03

        vol_ratio = signal.features.get("volume_ratio", 1.0)
        if vol_ratio > 1.5:
            adj += 0.03
        elif vol_ratio < 0.5:
            adj -= 0.05

        rsi = signal.features.get("rsi", 50.0)
        from core.enums import Direction
        if signal.direction == Direction.LONG and rsi < 30:
            adj += 0.03
        elif signal.direction == Direction.SHORT and rsi > 70:
            adj += 0.03

        return adj
