"""
Model Trainer.

Trains and calibrates the RandomForest classifier.

Pipeline:
1. Load / build dataset
2. Scale features (StandardScaler)
3. Balance classes (SMOTE)
4. Train RandomForest (with cross-validation)
5. Calibrate probabilities (CalibratedClassifierCV / Platt scaling)
6. Save to model registry path

Outputs:
  - Trained model artefact  →  ai/models/trading_model.joblib
  - Training report dict    →  returned to caller
"""
import os
import time
from typing import List, Dict, Tuple, Optional

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import (
    classification_report, roc_auc_score,
    precision_recall_curve, average_precision_score,
)

from app.training.dataset_builder import DatasetBuilder
from app.core.ai.features import FEATURE_NAMES
from app.utils.logger import get_logger

logger = get_logger("trainer")

DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "app", "core", "ai", "models", "trading_model.joblib",
)


class ModelTrainer:
    """
    Trains the RandomForest trade classifier end-to-end.
    """

    def __init__(
        self,
        model_path: str = None,
        n_estimators: int = 300,
        max_depth: int = 12,
        min_samples_leaf: int = 4,
        cv_folds: int = 5,
        calibrate: bool = True,
        random_seed: int = 42,
    ):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.cv_folds = cv_folds
        self.calibrate = calibrate
        self.random_seed = random_seed

        self._dataset_builder = DatasetBuilder()

    def train(
        self,
        features_list: List[Dict],
        labels: List[int],
        save: bool = True,
    ) -> dict:
        """
        Train on provided feature/label data.

        Returns a training report dict.
        """
        t0 = time.perf_counter()

        X, y = self._dataset_builder.to_arrays(features_list, labels)
        n_pos = int(y.sum())
        n_neg = int(len(y) - n_pos)
        logger.info(f"Training: {len(X)} samples | pos={n_pos} neg={n_neg}")

        if len(X) < 30:
            return {"error": "insufficient_samples", "n_samples": len(X)}

        # Feature scaling
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # SMOTE for class balance
        X_train, y_train = X_scaled, y
        if n_pos >= 6 and n_neg >= 6:
            try:
                from imblearn.over_sampling import SMOTE
                k = min(5, n_pos - 1, n_neg - 1)
                smote = SMOTE(random_state=self.random_seed, k_neighbors=k)
                X_train, y_train = smote.fit_resample(X_scaled, y)
                logger.info(f"After SMOTE: {len(X_train)} samples")
            except Exception as e:
                logger.warning(f"SMOTE skipped: {e}")

        # Base RandomForest
        base_rf = RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            max_features="sqrt",
            class_weight="balanced",
            n_jobs=-1,
            random_state=self.random_seed,
        )

        # Cross-validation on original (unsmoted) scaled data
        cv = StratifiedKFold(n_splits=min(self.cv_folds, max(2, n_pos // 2)), shuffle=True, random_state=self.random_seed)
        cv_auc_scores = cross_val_score(base_rf, X_scaled, y, cv=cv, scoring="roc_auc")
        cv_acc_scores = cross_val_score(base_rf, X_scaled, y, cv=cv, scoring="accuracy")
        logger.info(
            f"CV AUC: {cv_auc_scores.mean():.4f} ± {cv_auc_scores.std():.4f} | "
            f"Acc: {cv_acc_scores.mean():.4f}"
        )

        # Train on all data
        base_rf.fit(X_train, y_train)

        # Probability calibration (Platt scaling)
        if self.calibrate and len(np.unique(y)) == 2:
            n_folds_cal = min(3, max(2, n_pos // 3))
            model = CalibratedClassifierCV(base_rf, method="sigmoid", cv=n_folds_cal)
            model.fit(X_scaled, y)
        else:
            model = base_rf

        # Evaluate on full set (in-sample, for reporting)
        y_pred = model.predict(X_scaled)
        y_proba = model.predict_proba(X_scaled)[:, 1]

        try:
            auc = roc_auc_score(y, y_proba)
            ap = average_precision_score(y, y_proba)
        except Exception:
            auc = ap = 0.0

        report = classification_report(y, y_pred, output_dict=True, zero_division=0)

        # Feature importances (from base model if calibrated)
        _rf = base_rf if self.calibrate else model
        importances = {}
        if hasattr(_rf, "feature_importances_"):
            for name, imp in zip(FEATURE_NAMES, _rf.feature_importances_):
                importances[name] = round(float(imp), 5)
            importances = dict(sorted(importances.items(), key=lambda x: x[1], reverse=True))

        duration = time.perf_counter() - t0

        training_report = {
            "n_samples": len(X),
            "n_positive": n_pos,
            "n_negative": n_neg,
            "positive_rate": round(n_pos / len(X), 4),
            "cv_auc_mean": round(float(cv_auc_scores.mean()), 4),
            "cv_auc_std": round(float(cv_auc_scores.std()), 4),
            "cv_accuracy_mean": round(float(cv_acc_scores.mean()), 4),
            "full_auc": round(auc, 4),
            "avg_precision": round(ap, 4),
            "accuracy": round(float(report.get("accuracy", 0)), 4),
            "precision_1": round(float(report.get("1", {}).get("precision", 0)), 4),
            "recall_1": round(float(report.get("1", {}).get("recall", 0)), 4),
            "f1_1": round(float(report.get("1", {}).get("f1-score", 0)), 4),
            "top_features": dict(list(importances.items())[:15]),
            "training_time_s": round(duration, 2),
            "model_path": self.model_path,
            "calibrated": self.calibrate,
        }

        if save:
            self._save(model, scaler, training_report)

        return training_report

    async def train_from_db(
        self,
        days: int = 180,
        synthetic_boost: int = 500,
        save: bool = True,
    ) -> dict:
        """
        Convenience method: pull data from DB, optionally add synthetic,
        then train and save.
        """
        db_features, db_labels = await self._dataset_builder.from_database(days)

        if len(db_features) < 50:
            syn_n = max(synthetic_boost, 1000)
            logger.info(f"Augmenting with {syn_n} synthetic samples")
            syn_f, syn_l = self._dataset_builder.generate_synthetic(syn_n)
            features, labels = self._dataset_builder.merge(
                (db_features, db_labels), (syn_f, syn_l)
            )
        else:
            features, labels = db_features, db_labels

        return self.train(features, labels, save=save)

    def _save(self, model, scaler, report: dict):
        """Persist model + scaler + metadata."""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        artifact = {
            "model": model,
            "scaler": scaler,
            "feature_names": FEATURE_NAMES,
            "training_report": report,
            "version": _version_tag(),
        }
        joblib.dump(artifact, self.model_path, compress=3)
        logger.info(f"Model saved → {self.model_path}")

    def get_optimal_threshold(
        self,
        features_list: List[Dict],
        labels: List[int],
        target_precision: float = 0.60,
    ) -> float:
        """
        Find the confidence threshold that achieves at least `target_precision`.
        Useful for tuning MIN_CONFIDENCE.
        """
        X, y = self._dataset_builder.to_arrays(features_list, labels)
        if len(X) < 10:
            return 0.65

        artifact = joblib.load(self.model_path)
        model = artifact["model"]
        scaler = artifact.get("scaler")
        if scaler:
            X = scaler.transform(X)

        proba = model.predict_proba(X)[:, 1]
        precision, recall, thresholds = precision_recall_curve(y, proba)

        for p, r, t in zip(precision, recall, thresholds):
            if p >= target_precision and r > 0.1:
                return round(float(t), 3)
        return 0.65


def _version_tag() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
