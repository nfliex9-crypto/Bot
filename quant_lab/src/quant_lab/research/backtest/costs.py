from __future__ import annotations

import numpy as np


def transaction_costs(trades: np.ndarray, fee_bps: float) -> np.ndarray:
    fee = fee_bps / 10_000
    return np.abs(trades) * fee
