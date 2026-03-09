from __future__ import annotations

import numpy as np

from .risk_parity import risk_parity_weights
from .vol_target import apply_vol_target


def build_portfolio_weights(strategy_returns: np.ndarray, target_vol: float = 0.12) -> np.ndarray:
    cov = np.cov(strategy_returns)
    weights = risk_parity_weights(cov)
    # Neutralize directional bias at strategy-book level.
    weights = weights - np.mean(weights)
    if np.allclose(weights, 0.0):
        n = len(weights)
        weights = np.linspace(-1.0, 1.0, n)
    scaled = apply_vol_target(weights, cov, target_vol)
    gross = np.sum(np.abs(scaled))
    if gross > 0:
        scaled = scaled / gross
    return scaled
