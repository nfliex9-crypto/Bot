from __future__ import annotations

import numpy as np


def slippage_costs(trades: np.ndarray, slippage_bps: float, volatility: np.ndarray | None = None) -> np.ndarray:
    base = slippage_bps / 10_000
    if volatility is None:
        return np.abs(trades) * base
    scaled = base * (1 + np.nan_to_num(volatility, nan=0.0))
    return np.abs(trades) * scaled
