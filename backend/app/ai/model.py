from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier


FEATURE_ORDER = [
    "atr",
    "momentum",
    "sweep_strength",
    "bos_strength",
    "pullback_depth",
    "range_factor",
]


class AIModelService:
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model: RandomForestClassifier | None = None
        self._load()

    def _load(self) -> None:
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)

    def _vectorize(self, features: dict) -> list[float]:
        return [float(features.get(k, 0.0)) for k in FEATURE_ORDER]

    def predict_confidence(self, features: dict, strategy_score: float) -> float:
        if self.model is None:
            return float(min(max(0.45 + strategy_score * 0.5, 0.0), 1.0))

        x = np.array([self._vectorize(features)])
        proba = self.model.predict_proba(x)[0]
        if len(proba) == 1:
            return float(proba[0])
        return float(proba[1])

    def train(self, rows: list[dict]) -> dict:
        if len(rows) < 25:
            return {
                "trained": False,
                "reason": "not_enough_data",
                "samples": len(rows),
            }

        x = np.array([self._vectorize(row["features"]) for row in rows])
        y = np.array([int(row["label"]) for row in rows])

        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            random_state=42,
            class_weight="balanced_subsample",
        )
        model.fit(x, y)

        self.model = model
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self.model_path)

        return {
            "trained": True,
            "samples": len(rows),
            "positive_rate": float(y.mean()),
        }
