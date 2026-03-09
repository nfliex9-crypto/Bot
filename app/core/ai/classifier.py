"""
RandomForest Trade Classifier.

Classifies trade setups as profitable (1) or not (0) based on extracted features.
Also provides a confidence score (probability) for each prediction.

The model is trained on historical trade data where the outcome is known.
In production, it scores live setups before execution.
"""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score
from imblearn.over_sampling import SMOTE

from app.core.ai.features import FeatureEngineer, FEATURE_NAMES
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("classifier")


@dataclass
class PredictionResult:
    predicted_class: int = 0       # 0 = no trade, 1 = take trade
    confidence: float = 0.0        # Probability of success (0-1)
    should_trade: bool = False      # True if confidence >= threshold
    feature_importance: Optional[Dict[str, float]] = None


class TradeClassifier:
    """
    RandomForest classifier for trade setup quality scoring.

    Features are engineered from multi-timeframe analysis.
    Output is a confidence score that gates trade execution.
    """

    def __init__(
        self,
        model_path: str = None,
        min_confidence: float = None,
        n_estimators: int = 200,
        max_depth: int = 10,
        min_samples_leaf: int = 5,
    ):
        self.model_path = model_path or settings.MODEL_PATH
        self.min_confidence = min_confidence or settings.MIN_CONFIDENCE
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf

        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_engineer = FeatureEngineer()
        self.is_trained = False

        # Try to load existing model
        self._load_model()

    def predict(
        self,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
        mtf,  # MTFAnalysis
        session: str = "unknown",
    ) -> PredictionResult:
        """
        Score a trade setup.

        Returns a PredictionResult with confidence score and trading decision.
        Falls back to rule-based scoring if no model is loaded.
        """
        features = self.feature_engineer.extract(h1_df, m15_df, m5_df, mtf, session)

        if not self.is_trained:
            return self._rule_based_score(features, mtf)

        try:
            X = self.feature_engineer.to_array(features).reshape(1, -1)
            if self.scaler:
                X = self.scaler.transform(X)

            proba = self.model.predict_proba(X)[0]
            confidence = float(proba[1])  # Probability of class 1 (profitable)

            # Feature importance
            importance = {}
            if hasattr(self.model, "feature_importances_"):
                for name, imp in zip(FEATURE_NAMES, self.model.feature_importances_):
                    if imp > 0.01:
                        importance[name] = round(float(imp), 4)

            return PredictionResult(
                predicted_class=1 if confidence >= self.min_confidence else 0,
                confidence=round(confidence, 4),
                should_trade=confidence >= self.min_confidence,
                feature_importance=importance,
            )

        except Exception as e:
            logger.error(f"Classifier prediction error: {e}")
            return self._rule_based_score(features, mtf)

    def _rule_based_score(self, features: dict, mtf) -> PredictionResult:
        """
        Heuristic scoring when no trained model is available.
        Based on alignment score and key feature weights.
        """
        score = 0.0

        # MTF alignment is the most important factor
        score += features.get("alignment_score", 0.0) * 0.30

        # Sweep + BOS together
        if features.get("sweep_detected", 0) > 0 and features.get("bos_detected", 0) > 0:
            score += 0.20

        # Strong rejection
        score += features.get("sweep_rejection_strength", 0.0) * 0.10

        # BOS strength
        score += features.get("bos_strength", 0.0) * 0.10

        # Risk/Reward quality
        score += features.get("risk_reward", 0.0) * 0.10

        # FVG entry (highest confluence)
        score += features.get("entry_zone_fvg", 0.0) * 0.05

        # Session quality
        if features.get("is_overlap", 0) > 0:
            score += 0.05
        elif features.get("is_london", 0) > 0 or features.get("is_new_york", 0) > 0:
            score += 0.03

        # RSI confirmation
        rsi = features.get("rsi", 0.5)
        direction = 1 if features.get("bos_direction", 0) > 0 else -1
        if direction > 0 and rsi < 0.5:   # Bullish + oversold = good
            score += 0.05
        elif direction < 0 and rsi > 0.5:  # Bearish + overbought = good
            score += 0.05

        # Volume confirmation
        vol_ratio = features.get("volume_ratio", 1.0)
        if vol_ratio > 1.5:
            score += 0.05

        confidence = round(min(max(score, 0.0), 1.0), 4)

        return PredictionResult(
            predicted_class=1 if confidence >= self.min_confidence else 0,
            confidence=confidence,
            should_trade=confidence >= self.min_confidence,
            feature_importance=None,
        )

    def train(
        self,
        features_list: List[Dict[str, float]],
        labels: List[int],
        save: bool = True,
    ) -> dict:
        """
        Train the RandomForest classifier on historical trade data.

        Args:
            features_list: List of feature dicts (one per trade)
            labels: 1 = profitable trade, 0 = losing trade
            save: Whether to save model to disk

        Returns:
            Training metrics dict
        """
        if len(features_list) < 50:
            logger.warning(f"Insufficient training data: {len(features_list)} samples")
            return {"error": "insufficient_data", "n_samples": len(features_list)}

        X = np.array([
            self.feature_engineer.to_array(f) for f in features_list
        ])
        y = np.array(labels)

        # Replace NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=2.0, neginf=-2.0)

        logger.info(f"Training on {len(X)} samples, {y.sum()} positive ({y.mean():.1%})")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Handle class imbalance with SMOTE
        if y_train.sum() > 5 and (len(y_train) - y_train.sum()) > 5:
            try:
                smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
                X_train_scaled, y_train = smote.fit_resample(X_train_scaled, y_train)
                logger.info(f"After SMOTE: {len(X_train_scaled)} samples")
            except Exception as e:
                logger.warning(f"SMOTE failed: {e}, using raw data")

        # Train RandomForest
        self.model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True

        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_proba = self.model.predict_proba(X_test_scaled)[:, 1]

        try:
            auc = roc_auc_score(y_test, y_proba)
        except Exception:
            auc = 0.0

        report = classification_report(y_test, y_pred, output_dict=True)

        metrics = {
            "n_samples": len(X),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "auc_roc": round(auc, 4),
            "accuracy": round(report.get("accuracy", 0.0), 4),
            "precision_1": round(report.get("1", {}).get("precision", 0.0), 4),
            "recall_1": round(report.get("1", {}).get("recall", 0.0), 4),
            "f1_1": round(report.get("1", {}).get("f1-score", 0.0), 4),
        }

        logger.info(f"Training complete: AUC={metrics['auc_roc']:.4f} Acc={metrics['accuracy']:.4f}")

        if save:
            self._save_model()

        return metrics

    def _save_model(self):
        """Save model and scaler to disk."""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, "wb") as f:
                pickle.dump({"model": self.model, "scaler": self.scaler}, f)
            logger.info(f"Model saved to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")

    def _load_model(self):
        """
        Load model and scaler from disk.

        Search order:
        1. Configured model_path  (e.g. /app/models/rf_classifier.pkl)
        2. Training pipeline path  (app/core/ai/models/trading_model.joblib)
        3. Fall back to rule-based scoring — always safe.
        """
        candidate_paths = [self.model_path]

        # Also try the training-pipeline artefact location
        _training_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "core", "ai", "models", "trading_model.joblib",
        )
        if _training_path not in candidate_paths:
            candidate_paths.append(_training_path)

        for path in candidate_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                self.model = data.get("model")
                self.scaler = data.get("scaler")
                self.is_trained = self.model is not None
                if self.is_trained:
                    logger.info(f"AI model loaded from {path}")
                    return
            except Exception as e:
                logger.warning(f"Could not load model from {path}: {e}")

        logger.info(
            "No trained model found — using rule-based confidence scoring (safe fallback)"
        )
        self.is_trained = False

    def get_feature_importance(self) -> Dict[str, float]:
        """Return feature importances sorted by value."""
        if not self.is_trained or self.model is None:
            return {}
        importances = dict(zip(FEATURE_NAMES, self.model.feature_importances_))
        return dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))
