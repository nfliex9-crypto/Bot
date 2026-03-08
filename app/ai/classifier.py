from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from loguru import logger

try:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score
except ImportError:
    joblib = None  # type: ignore[assignment]
    RandomForestClassifier = None  # type: ignore[assignment, misc]
    cross_val_score = None  # type: ignore[assignment]

from app.ai.feature_engineer import FEATURE_NAMES, generate_synthetic_training_data, setup_to_features
from app.core.config import settings
from app.strategy.engine import TradeSetup


class TradeClassifier:
    """
    RandomForest-based trade confidence scorer.

    Predicts the probability that a trade setup will be profitable,
    and gates entries below a minimum confidence threshold.
    """

    def __init__(self) -> None:
        self._model: RandomForestClassifier | None = None
        self._min_confidence = settings.min_confidence
        self._model_path = Path(settings.ml_model_path)

    def load_or_train(self) -> None:
        if self._model_path.exists():
            self._model = joblib.load(self._model_path)
            logger.info(f"Loaded ML model from {self._model_path}")
            return

        logger.info("No saved model found — training on synthetic data")
        self.train_initial()

    def train_initial(self) -> None:
        if RandomForestClassifier is None:
            logger.error("scikit-learn not installed — ML disabled")
            return

        X, y = generate_synthetic_training_data(n_samples=3000)

        self._model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(X, y)

        scores = cross_val_score(self._model, X, y, cv=5, scoring="accuracy")
        logger.info(
            f"Model trained — CV accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})"
        )

        self._save()

    def retrain(self, X: np.ndarray, y: np.ndarray) -> float:
        """Retrain on accumulated real trade data. Returns CV accuracy."""
        if RandomForestClassifier is None or len(X) < 50:
            return 0.0

        self._model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(X, y)
        scores = cross_val_score(self._model, X, y, cv=min(5, len(X) // 10), scoring="accuracy")
        acc = float(scores.mean())
        logger.info(f"Model retrained on {len(X)} samples — CV accuracy: {acc:.3f}")
        self._save()
        return acc

    def predict_confidence(self, setup: TradeSetup) -> float:
        """Return win probability [0, 1] for a trade setup."""
        if self._model is None:
            return 0.5

        features = setup_to_features(setup)
        proba = self._model.predict_proba(features)[0]
        win_prob = float(proba[1]) if len(proba) > 1 else 0.5
        return win_prob

    def should_take_trade(self, setup: TradeSetup) -> tuple[bool, float]:
        """Returns (take_trade, confidence)."""
        confidence = self.predict_confidence(setup)
        return confidence >= self._min_confidence, confidence

    def get_feature_importance(self) -> dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(FEATURE_NAMES, self._model.feature_importances_))

    def _save(self) -> None:
        if self._model is None or joblib is None:
            return
        os.makedirs(self._model_path.parent, exist_ok=True)
        joblib.dump(self._model, self._model_path)
        logger.info(f"Model saved to {self._model_path}")
