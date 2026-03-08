"""
Random Forest Trade Classifier

Scores trade setups with a confidence probability using a Random Forest model.
The model is trained on historical trade data and predicts the probability that
a setup leads to a winning trade (price reaching at least TP1).

Includes:
- Model training with synthetic bootstrap data (for fresh installs)
- Inference with confidence scoring
- Feature importance reporting
- Model persistence via joblib
"""

import os
import logging
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict
from datetime import datetime

import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, roc_auc_score

from app.ai.features import extract_features, get_feature_names

logger = logging.getLogger(__name__)

MODEL_VERSION = "1.0.0"


class TradingClassifier:
    def __init__(self, model_path: str = "/app/models/rf_classifier.joblib"):
        self.model_path = model_path
        self.pipeline: Optional[Pipeline] = None
        self.feature_names = get_feature_names()
        self.is_trained = False
        self.model_version = MODEL_VERSION
        self._try_load()

    def _try_load(self):
        """Attempt to load a pre-trained model from disk."""
        if os.path.exists(self.model_path):
            try:
                self.pipeline = joblib.load(self.model_path)
                self.is_trained = True
                logger.info(f"Loaded model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
                self._bootstrap_train()
        else:
            logger.info("No saved model found, training bootstrap model...")
            self._bootstrap_train()

    def _bootstrap_train(self):
        """
        Train a bootstrap Random Forest on synthetically generated data.
        This ensures the system works out of the box. Replace with real
        historical trade data by calling train() with your dataset.
        """
        np.random.seed(42)
        n_samples = 2000
        n_features = len(self.feature_names)

        X = np.random.randn(n_samples, n_features).astype(np.float32)

        # Simulate: setups with good RSI, strong momentum, high setup_quality tend to win
        rsi = X[:, 0]         # rsi_14 (index 0)
        momentum = X[:, 19]   # momentum_1 (index 19)
        quality = X[:, 24]    # setup_quality (index 24)
        vol_ratio = X[:, 12]  # vol_ratio (index 12)

        score = (
            -0.3 * np.abs(rsi - 0)           # neutral RSI
            + 0.4 * momentum                  # positive momentum
            + 0.5 * quality                   # high setup quality
            + 0.2 * vol_ratio                 # volume confirmation
            + 0.1 * np.random.randn(n_samples)  # noise
        )
        y = (score > score.mean()).astype(int)

        self.train(X, y, save=True)
        logger.info("Bootstrap model trained and saved")

    def build_pipeline(self) -> Pipeline:
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5,
            max_features="sqrt",
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        return Pipeline([
            ("scaler", StandardScaler()),
            ("classifier", rf),
        ])

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        save: bool = True,
    ) -> Dict:
        """
        Train (or retrain) the classifier.

        Parameters
        ----------
        X : Feature matrix (n_samples, n_features)
        y : Binary labels (1 = winning trade, 0 = losing trade)
        save : Whether to save the model to disk

        Returns
        -------
        Training report dict
        """
        self.pipeline = self.build_pipeline()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        self.pipeline.fit(X_train, y_train)

        # Evaluate
        y_pred = self.pipeline.predict(X_test)
        y_proba = self.pipeline.predict_proba(X_test)[:, 1]

        cv_scores = cross_val_score(self.pipeline, X_train, y_train, cv=5, scoring="roc_auc")

        report = {
            "accuracy": float(np.mean(y_pred == y_test)),
            "roc_auc": float(roc_auc_score(y_test, y_proba)),
            "cv_roc_auc_mean": float(cv_scores.mean()),
            "cv_roc_auc_std": float(cv_scores.std()),
            "n_train": len(X_train),
            "n_test": len(X_test),
            "model_version": self.model_version,
            "trained_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Model trained: AUC={report['roc_auc']:.3f}, CV-AUC={report['cv_roc_auc_mean']:.3f}±{report['cv_roc_auc_std']:.3f}")

        self.is_trained = True

        if save:
            self._save_model()

        return report

    def predict(
        self,
        df: pd.DataFrame,
        signal_context: Optional[dict] = None,
    ) -> Tuple[float, Dict]:
        """
        Score a trade setup.

        Returns
        -------
        (confidence_score, feature_importance_dict)
        confidence_score: 0.0 - 1.0, probability of a winning trade
        """
        if not self.is_trained or self.pipeline is None:
            logger.warning("Model not trained, returning default confidence 0.5")
            return 0.5, {}

        features = extract_features(df, signal_context)
        if features is None:
            return 0.5, {}

        X = features.reshape(1, -1)
        try:
            proba = self.pipeline.predict_proba(X)[0]
            confidence = float(proba[1])  # Probability of winning class

            # Get feature importances
            rf_model = self.pipeline.named_steps["classifier"]
            importances = rf_model.feature_importances_
            feature_importance = {
                name: round(float(imp), 4)
                for name, imp in sorted(
                    zip(self.feature_names, importances),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            }

            return confidence, feature_importance
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return 0.5, {}

    def retrain_from_trades(self, trades_df: pd.DataFrame) -> Optional[Dict]:
        """
        Retrain the model from historical trade records.

        trades_df must have columns: features (list), won (bool)
        """
        if len(trades_df) < 50:
            logger.warning("Insufficient trade history for retraining (need >= 50)")
            return None

        X = np.array(trades_df["features"].tolist(), dtype=np.float32)
        y = trades_df["won"].astype(int).values
        return self.train(X, y, save=True)

    def _save_model(self):
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.pipeline, self.model_path)
        logger.info(f"Model saved to {self.model_path}")

    def get_model_info(self) -> Dict:
        return {
            "is_trained": self.is_trained,
            "model_version": self.model_version,
            "model_path": self.model_path,
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
        }
