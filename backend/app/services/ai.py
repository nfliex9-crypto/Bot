from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session
from sklearn.ensemble import RandomForestClassifier

from app.core.config import get_settings
from app.db.models import RecordStatus, Signal, Trade
from app.services.strategy import StrategySignal

settings = get_settings()


@dataclass
class AIScore:
    confidence: float
    source: str


class TradeAIService:
    FEATURE_COLUMNS = [
        "atr_ratio",
        "liquidity_sweep",
        "bos",
        "pullback_ratio",
        "trend_bias",
        "volume_zscore",
        "volatility",
    ]

    def score_signal(self, db: Session, signal: StrategySignal) -> AIScore:
        model = self._fit_model(db)
        vector = self._vectorize(signal.features)

        if model is None:
            confidence = self._heuristic_confidence(signal.features)
            return AIScore(confidence=confidence, source="heuristic")

        probability = float(model.predict_proba([vector])[0][1])
        return AIScore(confidence=round(probability, 4), source="random_forest")

    def _fit_model(self, db: Session) -> RandomForestClassifier | None:
        rows = (
            db.query(Signal, Trade)
            .join(Trade, Trade.signal_id == Signal.id)
            .filter(Trade.status.in_([RecordStatus.CLOSED, RecordStatus.SIMULATED, RecordStatus.OPEN]))
            .all()
        )
        if len(rows) < settings.ai_min_training_samples:
            return None

        features: list[list[float]] = []
        labels: list[int] = []
        for signal, trade in rows:
            features.append(self._vectorize(signal.features))
            labels.append(1 if trade.pnl >= 0 else 0)

        if len(set(labels)) < 2:
            return None

        model = RandomForestClassifier(
            n_estimators=150,
            max_depth=8,
            random_state=42,
            min_samples_split=4,
        )
        model.fit(features, labels)
        return model

    def _vectorize(self, features: dict[str, float | int]) -> list[float]:
        return [float(features.get(column, 0.0)) for column in self.FEATURE_COLUMNS]

    def _heuristic_confidence(self, features: dict[str, float | int]) -> float:
        score = 0.5
        score += 0.1 * float(features.get("liquidity_sweep", 0))
        score += 0.1 * float(features.get("bos", 0))
        score += 0.05 * float(features.get("pullback_ratio", 0.0))
        score += 0.05 * (1.0 if abs(float(features.get("trend_bias", 0))) > 0 else 0.0)
        score += 0.02 * max(0.0, float(features.get("volume_zscore", 0.0)))
        score -= 0.1 * min(float(features.get("volatility", 0.0)) * 100, 1.0)
        return round(float(np.clip(score, 0.05, 0.95)), 4)
