"""
Model Evaluator.

Evaluates a trained model against a held-out dataset:
  - ROC-AUC, PR-AUC
  - Calibration curve (how well probabilities reflect actual win rates)
  - Confusion matrix breakdown
  - Threshold sensitivity analysis
  - Feature importance ranking
  - Out-of-sample backtest performance (if backtest data provided)
"""
import os
from typing import List, Dict, Optional, Tuple
import numpy as np
import joblib

from app.training.dataset_builder import DatasetBuilder
from app.core.ai.features import FEATURE_NAMES
from app.utils.logger import get_logger

logger = get_logger("evaluator")


class ModelEvaluator:
    """
    Evaluates a persisted model artefact (joblib).
    """

    def __init__(self, model_path: str = None):
        from app.training.trainer import DEFAULT_MODEL_PATH
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self._ds_builder = DatasetBuilder()

    def evaluate(
        self,
        features_list: List[Dict],
        labels: List[int],
        thresholds: Optional[List[float]] = None,
    ) -> dict:
        """
        Run the full evaluation suite.

        Returns a comprehensive report dict suitable for logging / display.
        """
        if not os.path.exists(self.model_path):
            return {"error": "model_not_found", "path": self.model_path}

        artifact = joblib.load(self.model_path)
        model = artifact["model"]
        scaler = artifact.get("scaler")
        version = artifact.get("version", "unknown")

        X, y = self._ds_builder.to_arrays(features_list, labels)
        if scaler:
            X = scaler.transform(X)

        y_pred = model.predict(X)
        y_proba = model.predict_proba(X)[:, 1]

        # Core metrics
        from sklearn.metrics import (
            roc_auc_score, average_precision_score,
            confusion_matrix, classification_report,
        )
        try:
            auc = roc_auc_score(y, y_proba)
            ap = average_precision_score(y, y_proba)
        except Exception:
            auc = ap = 0.0

        cm = confusion_matrix(y, y_pred)
        tn, fp, fn, tp_ = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)

        report = classification_report(y, y_pred, output_dict=True, zero_division=0)

        # Threshold sensitivity
        thresholds = thresholds or [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
        threshold_results = []
        for thr in thresholds:
            preds = (y_proba >= thr).astype(int)
            n = preds.sum()
            if n == 0:
                threshold_results.append({"threshold": thr, "trades": 0})
                continue
            win_rate = float((preds * y).sum()) / n
            precision = float((preds * y).sum()) / (preds.sum() + 1e-10)
            threshold_results.append({
                "threshold": thr,
                "trades": int(n),
                "win_rate": round(win_rate, 4),
                "precision": round(precision, 4),
                "coverage": round(n / len(y), 4),
            })

        # Calibration (reliability diagram)
        calibration = self._calibration_curve(y, y_proba, n_bins=10)

        # Feature importance
        _rf = getattr(model, "estimator", model)
        importance = {}
        if hasattr(_rf, "feature_importances_"):
            for name, imp in zip(FEATURE_NAMES, _rf.feature_importances_):
                importance[name] = round(float(imp), 5)
            importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        return {
            "model_version": version,
            "model_path": self.model_path,
            "n_samples": len(X),
            "n_positive": int(y.sum()),
            "n_negative": int(len(y) - y.sum()),
            "roc_auc": round(auc, 4),
            "pr_auc": round(ap, 4),
            "accuracy": round(float(report.get("accuracy", 0)), 4),
            "precision": round(float(report.get("1", {}).get("precision", 0)), 4),
            "recall": round(float(report.get("1", {}).get("recall", 0)), 4),
            "f1": round(float(report.get("1", {}).get("f1-score", 0)), 4),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp_)},
            "threshold_analysis": threshold_results,
            "calibration": calibration,
            "feature_importance": dict(list(importance.items())[:20]),
        }

    def compare_versions(
        self,
        model_paths: List[str],
        features_list: List[Dict],
        labels: List[int],
    ) -> List[dict]:
        """Compare multiple saved model versions on the same test set."""
        results = []
        original_path = self.model_path
        for path in model_paths:
            self.model_path = path
            result = self.evaluate(features_list, labels)
            result["path"] = path
            results.append(result)
        self.model_path = original_path
        return sorted(results, key=lambda x: x.get("roc_auc", 0), reverse=True)

    def _calibration_curve(
        self,
        y_true: np.ndarray,
        y_prob: np.ndarray,
        n_bins: int = 10,
    ) -> List[dict]:
        """Compute calibration (reliability) curve."""
        bins = np.linspace(0, 1, n_bins + 1)
        result = []
        for i in range(n_bins):
            lo, hi = bins[i], bins[i + 1]
            mask = (y_prob >= lo) & (y_prob < hi)
            if mask.sum() == 0:
                continue
            mean_pred = float(y_prob[mask].mean())
            fraction_pos = float(y_true[mask].mean())
            result.append({
                "bin_mid": round((lo + hi) / 2, 2),
                "mean_predicted_prob": round(mean_pred, 4),
                "fraction_positive": round(fraction_pos, 4),
                "n_samples": int(mask.sum()),
            })
        return result
