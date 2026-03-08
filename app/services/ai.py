from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from app.core.config import Settings
from app.domain.models import FilterResult, MarketSnapshot, TradeSetup
from app.services.indicators import recent_range, volume_zscore, wick_ratio


class TradeFeatureEngineer:
    FEATURE_ORDER = [
        "strategy_score",
        "risk_per_unit",
        "atr_value",
        "h1_range",
        "m15_range",
        "m5_range",
        "m5_volume_zscore",
        "m5_wick_ratio",
        "filter_passed",
        "session_overlap",
        "direction_long",
    ]

    @classmethod
    def build(
        cls,
        setup: TradeSetup,
        snapshot: MarketSnapshot,
        filter_result: FilterResult,
    ) -> dict[str, float]:
        trigger_candle = snapshot.m5.iloc[-2]
        return {
            "strategy_score": float(setup.strategy_score),
            "risk_per_unit": float(setup.risk_per_unit),
            "atr_value": float(setup.atr_value),
            "h1_range": float(recent_range(snapshot.h1)),
            "m15_range": float(recent_range(snapshot.m15)),
            "m5_range": float(recent_range(snapshot.m5)),
            "m5_volume_zscore": float(volume_zscore(snapshot.m5)),
            "m5_wick_ratio": float(wick_ratio(trigger_candle)),
            "filter_passed": 1.0 if filter_result.passed else 0.0,
            "session_overlap": 1.0 if "overlap" in filter_result.session_label else 0.0,
            "direction_long": 1.0 if setup.direction.value == "long" else 0.0,
        }

    @classmethod
    def vectorize(cls, features: dict[str, float]) -> np.ndarray:
        return np.array([features.get(name, 0.0) for name in cls.FEATURE_ORDER], dtype=float)


class RandomForestConfidenceModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = Path(settings.model_path)
        self.model: RandomForestClassifier | None = None
        if self.path.exists():
            self.model = joblib.load(self.path)

    @property
    def is_trained(self) -> bool:
        return self.model is not None

    def score(self, features: dict[str, float], strategy_score: float) -> float:
        if not self.model:
            return round(min(max(strategy_score * 0.85 + 0.15, 0.0), 0.99), 4)
        vector = TradeFeatureEngineer.vectorize(features).reshape(1, -1)
        probability = float(self.model.predict_proba(vector)[0][1])
        blended = (probability * 0.7) + (strategy_score * 0.3)
        return round(min(max(blended, 0.0), 0.99), 4)

    def train(self, trade_rows: list[dict[str, object]]) -> dict[str, int | float | str]:
        usable_rows = [
            row
            for row in trade_rows
            if row.get("feature_vector")
            and row.get("realized_pnl") is not None
            and row.get("status") == "closed"
        ]
        if len(usable_rows) < self.settings.min_training_samples:
            raise ValueError(
                f"Need at least {self.settings.min_training_samples} closed trades with features to train"
            )

        usable_rows = usable_rows[-self.settings.max_training_rows :]
        x = np.vstack(
            [TradeFeatureEngineer.vectorize(row["feature_vector"]) for row in usable_rows]  # type: ignore[arg-type]
        )
        y = np.array([1 if float(row["realized_pnl"]) > 0 else 0 for row in usable_rows], dtype=int)

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=3,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(x, y)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self.path)
        self.model = model

        accuracy = float(model.score(x, y))
        return {
            "rows_used": len(usable_rows),
            "training_accuracy": round(accuracy, 4),
            "model_path": str(self.path),
        }
