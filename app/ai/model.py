from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


@dataclass(slots=True)
class ConfidenceResult:
    confidence: float
    accepted: bool


class TradeConfidenceModel:
    def __init__(self, model_path: str, min_confidence: float) -> None:
        self.model_path = Path(model_path)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        self.min_confidence = min_confidence
        self.model: RandomForestClassifier | None = None
        self._load()

    def _load(self) -> None:
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)

    def train(self, dataset: pd.DataFrame, target_col: str = "won") -> None:
        features = dataset.drop(columns=[target_col])
        target = dataset[target_col]
        model = RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_split=8,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(features, target)
        joblib.dump(model, self.model_path)
        self.model = model

    def _fallback_confidence(self, features: dict[str, float]) -> float:
        # Base confidence prior if model has not been trained yet.
        core = 0.5 + (features.get("structure_alignment", 0.0) * 0.2) + (features.get("session_score", 0.0) * 0.1)
        return float(np.clip(core, 0.0, 0.95))

    def score(self, features: dict[str, float]) -> ConfidenceResult:
        if self.model is None:
            confidence = self._fallback_confidence(features)
            return ConfidenceResult(confidence=confidence, accepted=confidence >= self.min_confidence)
        values = np.array([list(features.values())], dtype=float)
        probabilities = self.model.predict_proba(values)
        confidence = float(probabilities[0][1])
        return ConfidenceResult(confidence=confidence, accepted=confidence >= self.min_confidence)
