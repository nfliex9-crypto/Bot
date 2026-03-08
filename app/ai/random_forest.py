from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

logger = logging.getLogger(__name__)


class RandomForestConfidenceModel:
    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        self.model: Optional[RandomForestClassifier] = None
        self.feature_names: List[str] = []
        self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            return
        bundle = joblib.load(self.model_path)
        self.model = bundle["model"]
        self.feature_names = bundle["feature_names"]
        logger.info("Loaded AI model from %s", self.model_path)

    def _save(self) -> None:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "feature_names": self.feature_names}, self.model_path)
        logger.info("Saved AI model to %s", self.model_path)

    def is_trained(self) -> bool:
        return self.model is not None and len(self.feature_names) > 0

    def train(self, rows: Iterable[Tuple[Dict[str, float], int]]) -> tuple[int, Optional[float]]:
        items = list(rows)
        if len(items) < 2:
            return len(items), None

        self.feature_names = sorted({key for features, _ in items for key in features.keys()})
        x = np.array([[features.get(name, 0.0) for name in self.feature_names] for features, _ in items], dtype=float)
        y = np.array([label for _, label in items], dtype=int)

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=3,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(x, y)
        preds = model.predict(x)
        acc = float(accuracy_score(y, preds))
        self.model = model
        self._save()
        return len(items), acc

    def predict_confidence(self, features: Dict[str, float]) -> Optional[float]:
        if not self.is_trained():
            return None
        vec = np.array([[features.get(name, 0.0) for name in self.feature_names]], dtype=float)
        proba = self.model.predict_proba(vec)[0]
        return float(proba[1])

