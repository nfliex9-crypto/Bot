from __future__ import annotations

import numpy as np


def apply_vol_target(weights: np.ndarray, cov: np.ndarray, target_vol: float) -> np.ndarray:
    port_vol = float(np.sqrt(weights @ cov @ weights))
    if port_vol <= 1e-12:
        return weights
    scale = target_vol / port_vol
    return weights * scale
