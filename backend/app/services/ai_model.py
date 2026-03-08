from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier


class TradeConfidenceModel:
    def __init__(self) -> None:
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_split=4,
            random_state=42,
        )
        self._trained = False
        self._bootstrap_train()

    def _bootstrap_train(self) -> None:
        rng = np.random.default_rng(42)
        rows = 2500
        features = rng.normal(size=(rows, 5))

        # Synthetic win signal: stronger structure + moderate pullback + controlled ATR
        score = (
            features[:, 0] * 0.9
            + features[:, 1] * 1.0
            - np.abs(features[:, 2]) * 0.7
            - np.abs(features[:, 3]) * 0.4
            + features[:, 4] * 0.6
        )
        labels = (score > 0.2).astype(int)
        self.model.fit(features, labels)
        self._trained = True

    def score(self, feature_vector: list[float]) -> float:
        if not self._trained:
            return 0.5
        x = np.array(feature_vector, dtype=float).reshape(1, -1)
        probability = self.model.predict_proba(x)[0][1]
        return float(np.clip(probability, 0.01, 0.99))
