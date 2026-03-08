"""
RandomForest trade classifier.

Predicts trade outcome (win/loss) and provides confidence scoring.
The model is trained incrementally on historical trade outcomes.
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from ai.feature_engine import extract_features
from core.logger import get_logger

logger = get_logger("ai.classifier")

MODEL_DIR = Path("models")
MODEL_PATH = MODEL_DIR / "rf_classifier.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
MIN_TRAINING_SAMPLES = 30


class TradeClassifier:
    def __init__(self):
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: list = []
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        MODEL_DIR.mkdir(exist_ok=True)
        if MODEL_PATH.exists() and SCALER_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    self.model = pickle.load(f)
                with open(SCALER_PATH, "rb") as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                logger.info("Loaded existing ML model")
            except Exception as e:
                logger.warning(f"Could not load model: {e}")
                self._init_fresh()
        else:
            self._init_fresh()

    def _init_fresh(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self, features_df: pd.DataFrame, labels: np.ndarray) -> dict:
        """
        Train the model on historical trade data.
        features_df: DataFrame where each row is a trade's features.
        labels: 1 = winning trade, 0 = losing trade.
        """
        if len(features_df) < MIN_TRAINING_SAMPLES:
            logger.warning(
                f"Need {MIN_TRAINING_SAMPLES} samples, have {len(features_df)}"
            )
            return {"status": "insufficient_data", "samples": len(features_df)}

        self.feature_names = list(features_df.columns)
        X = features_df.values
        y = labels

        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.is_trained = True

        scores = cross_val_score(self.model, X_scaled, y, cv=min(5, len(y) // 5 or 2), scoring="accuracy")

        self._save_model()

        importances = dict(zip(self.feature_names, self.model.feature_importances_))
        top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]

        result = {
            "status": "trained",
            "samples": len(features_df),
            "cv_accuracy": float(np.mean(scores)),
            "cv_std": float(np.std(scores)),
            "top_features": top_features,
        }
        logger.info(f"Model trained: accuracy={result['cv_accuracy']:.3f} ± {result['cv_std']:.3f}")
        return result

    def predict(self, features: dict) -> Tuple[float, float]:
        """
        Predict trade outcome.
        Returns (probability_of_win, confidence_score).
        """
        if not self.is_trained:
            return 0.5, 0.5

        try:
            df = pd.DataFrame([features])
            if self.feature_names:
                for col in self.feature_names:
                    if col not in df.columns:
                        df[col] = 0.0
                df = df[self.feature_names]

            X = self.scaler.transform(df.values)
            proba = self.model.predict_proba(X)[0]

            win_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
            confidence = float(max(proba))

            return win_prob, confidence
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.5, 0.5

    def score_signal(
        self, h1: pd.DataFrame, m15: pd.DataFrame, m5: pd.DataFrame,
        base_confidence: float,
    ) -> Tuple[float, float]:
        """
        Score a trade signal using ML + base strategy confidence.
        Returns (combined_score, ai_score).
        """
        features = extract_features(h1, m15, m5)
        win_prob, ml_confidence = self.predict(features)

        if not self.is_trained:
            return base_confidence, 0.5

        ai_weight = 0.4
        strategy_weight = 0.6
        combined = strategy_weight * base_confidence + ai_weight * win_prob

        return min(combined, 1.0), win_prob

    def _save_model(self):
        MODEL_DIR.mkdir(exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(SCALER_PATH, "wb") as f:
            pickle.dump(self.scaler, f)
        logger.info("Model saved")
