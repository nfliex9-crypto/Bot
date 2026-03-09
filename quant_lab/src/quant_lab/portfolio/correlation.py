from __future__ import annotations

import numpy as np


def correlation_matrix(strategy_returns: np.ndarray) -> np.ndarray:
    if strategy_returns.ndim != 2:
        raise ValueError("strategy_returns must be shape (n_strategies, n_periods)")
    return np.corrcoef(strategy_returns)
