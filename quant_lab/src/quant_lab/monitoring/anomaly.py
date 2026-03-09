from __future__ import annotations

import numpy as np


def zscore_anomaly(x: np.ndarray, threshold: float = 3.0) -> np.ndarray:
    mu = np.nanmean(x)
    sd = np.nanstd(x)
    if sd == 0:
        return np.zeros_like(x, dtype=bool)
    z = (x - mu) / sd
    return np.abs(z) > threshold
