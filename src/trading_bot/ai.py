from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from .domain import TradeSignal
from .models import TradeRecord
from .strategy import displacement_score, liquidity_efficiency


class TradeConfidenceModel:
    FEATURE_NAMES = [
        "atr",
        "risk_distance",
        "bos_displacement",
        "pullback_depth",
        "liquidity_distance",
        "h1_alignment",
        "m15_alignment",
        "session_score",
        "displacement_score",
        "liquidity_efficiency",
    ]

    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path
        self.model = RandomForestClassifier(
            n_estimators=250,
            max_depth=6,
            min_samples_leaf=4,
            random_state=42,
        )
        self.is_trained = False
        self._load()

    def _load(self) -> None:
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)
            self.is_trained = True

    def _save(self) -> None:
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def feature_vector(self, signal: TradeSignal) -> np.ndarray:
        base = dict(signal.features)
        base["displacement_score"] = displacement_score(signal)
        base["liquidity_efficiency"] = liquidity_efficiency(signal)
        return np.array([float(base.get(name, 0.0)) for name in self.FEATURE_NAMES], dtype=float)

    def fit_from_records(self, records: list[TradeRecord]) -> bool:
        if len(records) < 30:
            return False

        vectors: list[np.ndarray] = []
        labels: list[int] = []
        for record in records:
            features = dict(record.metadata_json.get("features", {}))
            vector = np.array(
                [float(features.get(name, 0.0)) for name in self.FEATURE_NAMES],
                dtype=float,
            )
            vectors.append(vector)
            labels.append(1 if record.realized_pnl > 0 else 0)

        y = np.array(labels, dtype=int)
        if len(np.unique(y)) < 2:
            return False

        X = np.vstack(vectors)
        self.model.fit(X, y)
        self.is_trained = True
        self._save()
        return True

    def score(self, signal: TradeSignal) -> float:
        vector = self.feature_vector(signal).reshape(1, -1)
        if self.is_trained:
            probability = self.model.predict_proba(vector)[0, 1]
            return float(np.clip(probability, 0.0, 1.0))

        # Safe fallback before enough closed-trade history exists.
        heuristic = (
            (signal.features.get("h1_alignment", 0.0) * 0.25)
            + (signal.features.get("m15_alignment", 0.0) * 0.25)
            + min(displacement_score(signal) / 3.0, 0.25)
            + min(liquidity_efficiency(signal) / 4.0, 0.15)
            + (signal.features.get("session_score", 0.0) * 0.10)
        )
        return float(np.clip(heuristic, 0.0, 0.95))
