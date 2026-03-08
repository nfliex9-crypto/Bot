from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import Settings


class TradeConfidenceModel:
    FEATURE_ORDER = ["bias", "atr", "volatility_regime", "risk_distance", "bos_flag", "sweep_flag"]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_path = Path(settings.model_path)
        self.pipeline: Pipeline | None = None
        self._load_if_exists()

    def _load_if_exists(self) -> None:
        if self.model_path.exists():
            self.pipeline = joblib.load(self.model_path)

    def train_and_save(self, X: np.ndarray, y: np.ndarray) -> None:
        pipeline = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("rf", RandomForestClassifier(n_estimators=300, max_depth=8, random_state=42)),
            ]
        )
        pipeline.fit(X, y)
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.model_path)
        self.pipeline = pipeline

    def _feature_vector(self, features: dict) -> np.ndarray:
        vector = [float(features.get(name, 0.0)) for name in self.FEATURE_ORDER]
        return np.array([vector], dtype=float)

    def score(self, features: dict) -> float:
        x = self._feature_vector(features)
        if self.pipeline is None:
            # Safe fallback when a trained model artifact is not available yet.
            return float(np.clip(0.55 + (0.03 * features.get("bos_flag", 0)) + (0.03 * features.get("sweep_flag", 0)), 0, 1))
        proba = self.pipeline.predict_proba(x)
        return float(proba[0][1])

