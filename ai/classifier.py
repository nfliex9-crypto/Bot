from __future__ import annotations

import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from ai.feature_engineer import FeatureEngineer
from config.settings import settings
from core.models import Direction, MultiTimeframeAnalysis
from utils.logger import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)


def _label_trades(
    df: pd.DataFrame,
    direction: Direction,
    tp_pips: float,
    sl_pips: float,
    pip_size: float = 0.0001,
) -> pd.Series:
    """
    Create binary labels (1 = winner, 0 = loser) for historical bars.
    Simulates a trade entry at each bar and checks which outcome is hit first.
    """
    labels = pd.Series(0, index=df.index)
    tp_dist = tp_pips * pip_size
    sl_dist = sl_pips * pip_size

    for i in range(len(df) - 1):
        entry = df["close"].iloc[i]
        if direction == Direction.LONG:
            tp = entry + tp_dist
            sl = entry - sl_dist
        else:
            tp = entry - tp_dist
            sl = entry + sl_dist

        for j in range(i + 1, min(i + 30, len(df))):
            h = df["high"].iloc[j]
            lo = df["low"].iloc[j]
            if direction == Direction.LONG:
                if lo <= sl:
                    labels.iloc[i] = 0
                    break
                if h >= tp:
                    labels.iloc[i] = 1
                    break
            else:
                if h >= sl:
                    labels.iloc[i] = 0
                    break
                if lo <= tp:
                    labels.iloc[i] = 1
                    break
    return labels


class TradeClassifier:
    """
    RandomForest-based trade quality classifier.

    Predicts the probability that a trade setup will be profitable
    given the current market features (confidence score 0–1).
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self._engineer = FeatureEngineer()
        self._pipeline: Optional[Pipeline] = None
        self._version: str = ""
        self._model_path: Optional[Path] = None
        self._load_or_init()

    # ------------------------------------------------------------------
    def predict_confidence(
        self,
        df: pd.DataFrame,
        mta: Optional[MultiTimeframeAnalysis] = None,
        session_flags: Optional[Dict[str, bool]] = None,
    ) -> float:
        """
        Returns a confidence score in [0, 1].
        If no model is trained, returns 0.5 (neutral).
        """
        if self._pipeline is None:
            return 0.5

        features = self._engineer.build(df, mta, session_flags)
        if features is None:
            return 0.5

        try:
            proba = self._pipeline.predict_proba(features.reshape(1, -1))[0]
            return float(proba[1])   # probability of class 1 (winner)
        except Exception as exc:
            logger.warning("Classifier prediction failed for %s: %s", self.symbol, exc)
            return 0.5

    # ------------------------------------------------------------------
    def train(
        self,
        df: pd.DataFrame,
        direction: Direction,
        atr_tp_mult: float = 1.5,
        atr_sl_mult: float = 1.0,
    ) -> Dict[str, float]:
        """
        Train the classifier on historical OHLCV data.
        Returns evaluation metrics.
        """
        if len(df) < 200:
            logger.warning("Not enough data to train classifier for %s", self.symbol)
            return {}

        logger.info("Training classifier for %s (%s bars)...", self.symbol, len(df))

        atr_series = df["close"].rolling(14).std().fillna(0.0)
        mean_atr_pips = float(atr_series.mean() / 0.0001)
        tp_pips = mean_atr_pips * atr_tp_mult
        sl_pips = mean_atr_pips * atr_sl_mult

        pip_size = 0.01 if "JPY" in self.symbol.upper() else 0.0001
        labels = _label_trades(df, direction, tp_pips, sl_pips, pip_size)

        X = self._engineer.build_batch(df)
        y = labels.iloc[60:].values   # align with batch builder offset

        if len(X) != len(y):
            min_len = min(len(X), len(y))
            X, y = X[:min_len], y[:min_len]

        # Remove NaN rows
        valid_mask = ~np.any(np.isnan(X), axis=1)
        X, y = X[valid_mask], y[valid_mask]

        if len(np.unique(y)) < 2:
            logger.warning("Only one class in labels for %s, skipping train", self.symbol)
            return {}

        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_split=20,
            min_samples_leaf=10,
            max_features="sqrt",
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        calibrated = CalibratedClassifierCV(rf, method="sigmoid", cv=3)
        pipeline = Pipeline([("scaler", StandardScaler()), ("clf", calibrated)])

        # Cross-validated metrics
        cv_scores = cross_val_score(pipeline, X, y, cv=StratifiedKFold(3), scoring="f1")
        pipeline.fit(X, y)

        y_pred = pipeline.predict(X)
        metrics = {
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, zero_division=0),
            "recall": recall_score(y, y_pred, zero_division=0),
            "f1_score": float(np.mean(cv_scores)),
            "n_samples": int(len(y)),
        }

        self._pipeline = pipeline
        self._version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._save(metrics)

        logger.info(
            "Classifier trained for %s | acc=%.3f | f1=%.3f | n=%d",
            self.symbol,
            metrics["accuracy"],
            metrics["f1_score"],
            metrics["n_samples"],
        )
        return metrics

    # ------------------------------------------------------------------
    def _load_or_init(self) -> None:
        model_file = MODELS_DIR / f"classifier_{self.symbol}.pkl"
        if model_file.exists():
            try:
                with open(model_file, "rb") as f:
                    data = pickle.load(f)
                self._pipeline = data["pipeline"]
                self._version = data.get("version", "unknown")
                self._model_path = model_file
                logger.info("Loaded classifier for %s (v%s)", self.symbol, self._version)
                return
            except Exception as exc:
                logger.warning("Could not load classifier for %s: %s", self.symbol, exc)
        self._pipeline = None
        logger.info("No trained classifier found for %s — will use neutral score", self.symbol)

    def _save(self, metrics: Dict[str, float]) -> None:
        model_file = MODELS_DIR / f"classifier_{self.symbol}.pkl"
        with open(model_file, "wb") as f:
            pickle.dump(
                {
                    "pipeline": self._pipeline,
                    "version": self._version,
                    "symbol": self.symbol,
                    "metrics": metrics,
                    "feature_names": FeatureEngineer.FEATURE_NAMES,
                },
                f,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        self._model_path = model_file

    def is_trained(self) -> bool:
        return self._pipeline is not None

    @property
    def version(self) -> str:
        return self._version


class ClassifierRegistry:
    """Thread-safe registry of per-symbol classifiers."""

    def __init__(self) -> None:
        self._classifiers: Dict[str, TradeClassifier] = {}

    def get(self, symbol: str) -> TradeClassifier:
        if symbol not in self._classifiers:
            self._classifiers[symbol] = TradeClassifier(symbol)
        return self._classifiers[symbol]

    def predict(
        self,
        symbol: str,
        df: pd.DataFrame,
        mta: Optional[MultiTimeframeAnalysis] = None,
        session_flags: Optional[Dict[str, bool]] = None,
    ) -> float:
        return self.get(symbol).predict_confidence(df, mta, session_flags)

    async def retrain_all(
        self,
        data_feeds: Dict[str, pd.DataFrame],
        direction: Direction = Direction.LONG,
    ) -> Dict[str, Dict]:
        results = {}
        for symbol, df in data_feeds.items():
            clf = self.get(symbol)
            results[symbol] = clf.train(df, direction)
        return results


# Module-level singleton
classifier_registry = ClassifierRegistry()
