"""
RandomForest Trade Classifier.

Scores each MTFSignal with a confidence probability [0, 1].
Higher score = AI believes the trade will be profitable.

Training data is built from historical closed trades stored in PostgreSQL.
The model is retrained periodically (default: every 24 hours).
"""

import os
import pickle
from datetime import datetime, timezone
from typing import Optional, Tuple, List
import numpy as np
from loguru import logger

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import cross_val_score, StratifiedKFold
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import classification_report
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available")

from src.ai.feature_engineering import extract_features, FEATURE_NAMES, N_FEATURES
from src.strategy.multi_timeframe import MTFSignal
from config.settings import settings


MODEL_PATH = os.path.join("data", "models", "rf_classifier.joblib")
SCALER_PATH = os.path.join("data", "models", "scaler.joblib")
MIN_TRAINING_SAMPLES = 30


class TradeClassifier:
    """
    Wraps a RandomForest pipeline for trade confidence scoring.
    Falls back to rule-based scoring when insufficient training data.
    """

    def __init__(self):
        self._model: Optional[object] = None
        self._trained = False
        self._last_trained: Optional[datetime] = None
        self._training_samples: int = 0
        self._cv_score: float = 0.0

        # Try to load pre-trained model
        self._load_model()

    # ── Scoring ───────────────────────────────────────────────────────────────

    def predict_confidence(self, signal: MTFSignal) -> float:
        """
        Return trade confidence score in [0, 1].
        Uses ML model if trained, else falls back to rule-based score.
        """
        features = extract_features(signal)

        if self._trained and self._model is not None and SKLEARN_AVAILABLE:
            try:
                proba = self._model.predict_proba(features.reshape(1, -1))[0]
                # proba[1] = probability of class 1 (profitable trade)
                ml_confidence = float(proba[1])
                # Blend with composite score for stability
                blended = 0.6 * ml_confidence + 0.4 * signal.confidence
                return round(blended, 4)
            except Exception as e:
                logger.warning(f"ML predict failed, using rule-based: {e}")

        # Rule-based fallback
        return self._rule_based_score(signal)

    def _rule_based_score(self, signal: MTFSignal) -> float:
        """
        Heuristic confidence score when model is not yet trained.
        Weights the pre-computed composite signal confidence.
        """
        score = signal.confidence

        # Bonus for high-quality setups
        if signal.ltf.sweep.detected and signal.ltf.sweep.direction == signal.direction:
            score = min(score + 0.05, 1.0)
        if signal.ltf.pullback.entry_type == "order_block":
            score = min(score + 0.05, 1.0)
        if signal.mtf.bos.detected:
            score = min(score + 0.03, 1.0)
        if signal.risk_reward and signal.risk_reward >= 2.0:
            score = min(score + 0.05, 1.0)

        return round(score, 4)

    # ── Training ──────────────────────────────────────────────────────────────

    def train(
        self,
        feature_matrix: np.ndarray,
        labels: np.ndarray,
        retrain_from_scratch: bool = True,
    ) -> dict:
        """
        Train the RandomForest classifier.

        Args:
            feature_matrix: (N, N_FEATURES) float array
            labels: (N,) binary array — 1 = profitable trade, 0 = losing trade
            retrain_from_scratch: if True, create a fresh model

        Returns:
            Training report dict
        """
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available; cannot train")
            return {"error": "sklearn not available"}

        n_samples = len(labels)
        if n_samples < MIN_TRAINING_SAMPLES:
            logger.warning(f"Not enough training samples: {n_samples} < {MIN_TRAINING_SAMPLES}")
            return {"error": f"Need at least {MIN_TRAINING_SAMPLES} samples, got {n_samples}"}

        n_positive = int(labels.sum())
        n_negative = n_samples - n_positive
        logger.info(f"Training RF classifier | samples={n_samples} pos={n_positive} neg={n_negative}")

        if retrain_from_scratch or self._model is None:
            rf = RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                min_samples_split=10,
                min_samples_leaf=5,
                max_features="sqrt",
                class_weight="balanced",
                random_state=42,
                n_jobs=-1,
            )
            # Calibrate probabilities using isotonic regression
            calibrated_rf = CalibratedClassifierCV(rf, cv=3, method="isotonic")
            self._model = Pipeline([
                ("scaler", StandardScaler()),
                ("classifier", calibrated_rf),
            ])

        self._model.fit(feature_matrix, labels)

        # Cross-validation
        cv = StratifiedKFold(n_splits=min(5, n_positive), shuffle=True, random_state=42)
        cv_scores = cross_val_score(self._model, feature_matrix, labels, cv=cv, scoring="roc_auc")
        self._cv_score = float(cv_scores.mean())

        self._trained = True
        self._last_trained = datetime.now(tz=timezone.utc)
        self._training_samples = n_samples

        # Save model
        self._save_model()

        preds = self._model.predict(feature_matrix)
        report = classification_report(labels, preds, output_dict=True)

        logger.info(f"RF trained | cv_auc={self._cv_score:.4f} | accuracy={report['accuracy']:.4f}")
        return {
            "trained": True,
            "samples": n_samples,
            "cv_auc": self._cv_score,
            "accuracy": report["accuracy"],
            "precision_1": report.get("1", {}).get("precision", 0),
            "recall_1": report.get("1", {}).get("recall", 0),
        }

    def build_training_data_from_trades(self, trades: list) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert closed trade records + their stored features into training data.
        A trade is labelled 1 (positive) if realized_pnl > 0, else 0.
        """
        features_list = []
        labels = []

        for trade in trades:
            if trade.get("ai_features") and trade.get("realized_pnl") is not None:
                feat_dict = trade["ai_features"]
                try:
                    feat_vector = np.array(
                        [feat_dict.get(name, 0.0) for name in FEATURE_NAMES], dtype=np.float64
                    )
                    feat_vector = np.nan_to_num(feat_vector)
                    features_list.append(feat_vector)
                    labels.append(1 if float(trade["realized_pnl"]) > 0 else 0)
                except Exception as e:
                    logger.warning(f"Skipping trade feature extraction: {e}")

        if not features_list:
            return np.array([]).reshape(0, N_FEATURES), np.array([])

        return np.vstack(features_list), np.array(labels)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_model(self) -> None:
        if not SKLEARN_AVAILABLE or self._model is None:
            return
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(self._model, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")

    def _load_model(self) -> None:
        if not SKLEARN_AVAILABLE:
            return
        if os.path.exists(MODEL_PATH):
            try:
                self._model = joblib.load(MODEL_PATH)
                self._trained = True
                logger.info(f"Pre-trained model loaded from {MODEL_PATH}")
            except Exception as e:
                logger.warning(f"Could not load saved model: {e}")

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "trained": self._trained,
            "last_trained": self._last_trained.isoformat() if self._last_trained else None,
            "training_samples": self._training_samples,
            "cv_auc": self._cv_score,
            "sklearn_available": SKLEARN_AVAILABLE,
            "model_path": MODEL_PATH if os.path.exists(MODEL_PATH) else None,
        }
