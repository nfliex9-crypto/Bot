from __future__ import annotations

import numpy as np


def risk_parity_weights(cov: np.ndarray, n_iter: int = 500, lr: float = 0.01) -> np.ndarray:
    n = cov.shape[0]
    w = np.ones(n) / n
    for _ in range(n_iter):
        port_var = w @ cov @ w
        marginal = cov @ w
        risk_contrib = w * marginal
        target = port_var / n
        grad = risk_contrib - target
        w = w - lr * grad
        w = np.clip(w, 1e-8, None)
        w /= w.sum()
    return w
