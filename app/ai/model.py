from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


FEATURE_COLUMNS = [
    "h1_volatility",
    "m15_sweep_depth",
    "m15_bos_distance",
    "m5_entry_quality",
    "atr_ratio",
    "bias_alignment",
    "session_score",
    "news_risk",
]


@dataclass(slots=True)
class ModelScore:
    confidence: float
    source: str


class RandomForestConfidenceModel:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.pipeline: Pipeline | None = None
        if self.model_path.exists():
            self.pipeline = joblib.load(self.model_path)

    def is_trained(self) -> bool:
        return self.pipeline is not None

    def train(self, dataset: pd.DataFrame, label_column: str = "label") -> None:
        frame = dataset.copy()
        for column in FEATURE_COLUMNS:
            if column not in frame.columns:
                frame[column] = 0.0
        classifier = RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=3,
            random_state=42,
            class_weight="balanced",
        )
        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("classifier", classifier),
            ]
        )
        pipeline.fit(frame[FEATURE_COLUMNS], frame[label_column].astype(int))
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(pipeline, self.model_path)
        self.pipeline = pipeline

    def score(self, feature_map: dict[str, float], fallback: float) -> ModelScore:
        row = {column: float(feature_map.get(column, 0.0)) for column in FEATURE_COLUMNS}
        if self.pipeline is None:
            return ModelScore(confidence=float(fallback), source="heuristic")
        frame = pd.DataFrame([row], columns=FEATURE_COLUMNS)
        probability = float(self.pipeline.predict_proba(frame)[0][1])
        confidence = max(0.0, min(probability, 0.99))
        return ModelScore(confidence=confidence, source="random_forest")

    def sample_training_frame(self) -> pd.DataFrame:
        sample_rows: list[dict[str, Any]] = [
            {
                "h1_volatility": 0.0012,
                "m15_sweep_depth": 0.85,
                "m15_bos_distance": 1.1,
                "m5_entry_quality": 0.82,
                "atr_ratio": 0.0007,
                "bias_alignment": 1.0,
                "session_score": 1.0,
                "news_risk": 0.0,
                "label": 1,
            },
            {
                "h1_volatility": 0.0024,
                "m15_sweep_depth": 0.18,
                "m15_bos_distance": 0.2,
                "m5_entry_quality": 0.31,
                "atr_ratio": 0.0018,
                "bias_alignment": 0.5,
                "session_score": 0.4,
                "news_risk": 1.0,
                "label": 0,
            },
            {
                "h1_volatility": 0.0016,
                "m15_sweep_depth": 0.62,
                "m15_bos_distance": 0.9,
                "m5_entry_quality": 0.76,
                "atr_ratio": 0.0009,
                "bias_alignment": 1.0,
                "session_score": 0.8,
                "news_risk": 0.0,
                "label": 1,
            },
        ]
        return pd.DataFrame(sample_rows)
