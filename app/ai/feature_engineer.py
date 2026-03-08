from __future__ import annotations

import numpy as np

from app.strategy.engine import TradeSetup

FEATURE_NAMES = [
    "direction",
    "h1_bias_aligned",
    "m15_bos_count",
    "m5_bos_count",
    "pullback_distance_atr",
    "atr_value",
    "rsi_m5",
    "ema_distance",
    "sweep_wick_size",
]


def setup_to_features(setup: TradeSetup) -> np.ndarray:
    """Convert a TradeSetup's confidence_features dict to a fixed-order feature vector."""
    return np.array(
        [setup.confidence_features.get(name, 0.0) for name in FEATURE_NAMES],
        dtype=np.float64,
    ).reshape(1, -1)


def generate_synthetic_training_data(n_samples: int = 2000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data that mimics realistic trade feature distributions.
    Used to bootstrap the RandomForest model before live data accumulates.
    """
    rng = np.random.RandomState(seed)

    X = np.column_stack(
        [
            rng.choice([0.0, 1.0], size=n_samples),                 # direction
            rng.choice([0.0, 1.0], size=n_samples, p=[0.2, 0.8]),   # h1_bias_aligned
            rng.randint(0, 8, size=n_samples).astype(float),         # m15_bos_count
            rng.randint(0, 6, size=n_samples).astype(float),         # m5_bos_count
            rng.uniform(0.1, 2.0, size=n_samples),                   # pullback_distance_atr
            rng.uniform(0.0001, 0.05, size=n_samples),               # atr_value
            rng.uniform(20, 80, size=n_samples),                     # rsi_m5
            rng.uniform(0, 3.0, size=n_samples),                     # ema_distance
            rng.uniform(0, 0.01, size=n_samples),                    # sweep_wick_size
        ]
    )

    # Winning probability increases with alignment and moderate RSI
    bias_score = X[:, 1] * 0.3
    bos_score = np.clip(X[:, 2] / 5.0, 0, 0.2)
    pullback_score = np.where(X[:, 4] < 1.0, 0.2, 0.0)
    rsi_score = np.where((X[:, 6] > 30) & (X[:, 6] < 70), 0.15, 0.0)

    win_prob = np.clip(0.2 + bias_score + bos_score + pullback_score + rsi_score, 0.1, 0.9)
    y = (rng.random(n_samples) < win_prob).astype(int)

    return X, y
