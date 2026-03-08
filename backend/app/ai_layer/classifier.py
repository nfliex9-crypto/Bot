"""
Trade Classifier

Random Forest-based classifier that scores trade setups for confidence.
Trains on historical trade outcomes and provides probability estimates.
"""

import os
import pickle
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, classification_report
)
from sklearn.preprocessing import StandardScaler

from app.ai_layer.feature_engineering import FeatureEngineer
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "trade_classifier.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")


class TradeClassifier:
    """Random Forest classifier for trade quality scoring."""

    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.model_version: str = ""
        self.metrics: dict = {}
        self._ensure_model_dir()

    def _ensure_model_dir(self):
        os.makedirs(MODEL_DIR, exist_ok=True)

    def train(
        self,
        df: pd.DataFrame,
        forward_bars: int = 20,
        profit_threshold: float = 0.005,
        test_size: float = 0.2,
        n_estimators: int = 200,
        max_depth: int = 10,
        min_samples_leaf: int = 20,
    ) -> dict:
        """Train the Random Forest classifier on historical data."""
        logger.info("Starting model training", bars=len(df))

        features = self.feature_engineer.extract_features(df)
        labels = self.feature_engineer.create_labels(df, forward_bars, profit_threshold)

        valid_mask = labels.notna() & (features.notna().all(axis=1))
        features = features[valid_mask]
        labels = labels[valid_mask]

        if len(features) < 100:
            logger.warning("Insufficient training data", samples=len(features))
            return {"error": "Insufficient data", "samples": len(features)}

        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=test_size, shuffle=False
        )

        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

        self.model.fit(X_train_scaled, y_train)

        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        f1 = f1_score(y_test, y_pred, zero_division=0)

        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train, cv=5, scoring="f1"
        )

        feature_importance = dict(zip(
            features.columns,
            self.model.feature_importances_
        ))
        top_features = dict(sorted(
            feature_importance.items(), key=lambda x: x[1], reverse=True
        )[:10])

        self.model_version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.metrics = {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "cv_f1_mean": round(cv_scores.mean(), 4),
            "cv_f1_std": round(cv_scores.std(), 4),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "top_features": top_features,
            "model_version": self.model_version,
        }

        self.save_model()

        logger.info(
            "Model training complete",
            accuracy=accuracy, precision=precision, recall=recall, f1=f1,
            version=self.model_version,
        )

        return self.metrics

    def predict_confidence(self, df: pd.DataFrame, idx: int = -1) -> float:
        """Predict trade confidence for a specific bar."""
        if self.model is None:
            self._load_or_create_default()

        features = self.feature_engineer.extract_features(df)
        if features.empty:
            return 0.5

        row = features.iloc[idx:idx + 1] if idx != -1 else features.iloc[-1:]
        row_scaled = self.scaler.transform(row) if self.scaler else row.values

        try:
            probabilities = self.model.predict_proba(row_scaled)
            confidence = probabilities[0][1]
            return round(float(confidence), 4)
        except Exception as e:
            logger.error("Prediction failed", error=str(e))
            return 0.5

    def predict_batch(self, df: pd.DataFrame) -> np.ndarray:
        """Predict confidence for all bars in the dataframe."""
        if self.model is None:
            self._load_or_create_default()

        features = self.feature_engineer.extract_features(df)
        if features.empty:
            return np.full(len(df), 0.5)

        scaled = self.scaler.transform(features) if self.scaler else features.values

        try:
            probabilities = self.model.predict_proba(scaled)
            return probabilities[:, 1]
        except Exception as e:
            logger.error("Batch prediction failed", error=str(e))
            return np.full(len(features), 0.5)

    def score_setup(
        self,
        df: pd.DataFrame,
        direction: str,
        strategy_name: str,
        setup_confidence: float,
    ) -> float:
        """Score a trade setup combining strategy confidence with ML prediction."""
        ml_confidence = self.predict_confidence(df)
        combined = (setup_confidence * 0.6) + (ml_confidence * 0.4)
        return round(min(1.0, combined), 4)

    def save_model(self) -> None:
        if self.model is not None:
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(self.model, f)
            logger.info("Model saved", path=MODEL_PATH)
        if self.scaler is not None:
            with open(SCALER_PATH, "wb") as f:
                pickle.dump(self.scaler, f)

    def load_model(self) -> bool:
        try:
            with open(MODEL_PATH, "rb") as f:
                self.model = pickle.load(f)
            with open(SCALER_PATH, "rb") as f:
                self.scaler = pickle.load(f)
            logger.info("Model loaded", path=MODEL_PATH)
            return True
        except FileNotFoundError:
            logger.warning("No saved model found")
            return False

    def _load_or_create_default(self) -> None:
        """Load saved model or create a default untrained model."""
        if not self.load_model():
            logger.info("Creating default model with synthetic data")
            self._create_default_model()

    def _create_default_model(self) -> None:
        """Create a default model trained on synthetic data for bootstrapping."""
        np.random.seed(42)
        n_features = len(FeatureEngineer.FEATURE_COLUMNS)
        n_samples = 1000

        X = np.random.randn(n_samples, n_features)
        y = (np.random.rand(n_samples) > 0.5).astype(int)

        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        self.model = RandomForestClassifier(
            n_estimators=50, max_depth=5,
            min_samples_leaf=20, random_state=42, n_jobs=-1,
        )
        self.model.fit(X_scaled, y)
        self.model_version = "v0_default"
        self.save_model()

    def get_feature_importance(self) -> dict:
        if self.model is None:
            return {}
        feature_names = FeatureEngineer.FEATURE_COLUMNS + [
            "direction_long", "strategy_bos", "strategy_sweep", "strategy_pullback"
        ]
        n = min(len(feature_names), len(self.model.feature_importances_))
        importance = dict(zip(feature_names[:n], self.model.feature_importances_[:n]))
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
