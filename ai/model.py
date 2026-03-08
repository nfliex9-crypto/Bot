from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import cross_val_score

from ai.features import FEATURE_COLUMNS, signal_features_to_array, trades_to_training_data
from config.settings import settings

logger = logging.getLogger(__name__)


class TradingAIModel:
    """RandomForest classifier that scores trade signal quality."""

    def __init__(self) -> None:
        self._model: Optional[RandomForestClassifier] = None
        self._model_path = Path(settings.ai_model_path)
        self._is_trained = False
        self._load_model()

    def _load_model(self) -> None:
        if self._model_path.exists():
            try:
                self._model = joblib.load(self._model_path)
                self._is_trained = True
                logger.info("AI model loaded from %s", self._model_path)
            except Exception:
                logger.exception("Failed to load AI model")
                self._model = None

    def train(self, trades: list[Dict]) -> Optional[Dict]:
        X, y = trades_to_training_data(trades)
        if X is None or y is None:
            logger.info("Not enough training data (%d trades required)", 20)
            return None

        logger.info("Training AI model with %d samples", len(X))

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_split=5,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

        cv_scores = cross_val_score(model, X, y, cv=min(5, len(X) // 5 or 2), scoring="f1")
        model.fit(X, y)

        y_pred = model.predict(X)
        metrics = {
            "accuracy": float(accuracy_score(y, y_pred)),
            "precision": float(precision_score(y, y_pred, zero_division=0)),
            "recall": float(recall_score(y, y_pred, zero_division=0)),
            "f1_score": float(f1_score(y, y_pred, zero_division=0)),
            "cv_f1_mean": float(np.mean(cv_scores)),
            "training_samples": len(X),
            "feature_importances": dict(zip(FEATURE_COLUMNS, model.feature_importances_.tolist())),
        }

        self._model = model
        self._is_trained = True

        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, self._model_path)
        logger.info("AI model trained — F1: %.3f, CV-F1: %.3f", metrics["f1_score"], metrics["cv_f1_mean"])

        return metrics

    def predict_confidence(self, features: Dict[str, float]) -> float:
        if not self._is_trained or self._model is None:
            return 0.75

        try:
            X = signal_features_to_array(features)
            proba = self._model.predict_proba(X)
            return float(proba[0][1])
        except Exception:
            logger.exception("AI prediction failed")
            return 0.5

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def get_feature_importances(self) -> Dict[str, float]:
        if self._model is None:
            return {}
        return dict(zip(FEATURE_COLUMNS, self._model.feature_importances_.tolist()))
