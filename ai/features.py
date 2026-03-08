from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "atr_m5",
    "atr_m15",
    "atr_h1",
    "rsi",
    "volume_ratio",
    "body_ratio",
    "ema_spread",
    "bias_bullish",
    "bias_bearish",
    "signal_liquidity",
    "signal_bos",
    "signal_pullback",
    "risk_reward",
    "num_liquidity_zones",
]


def signal_features_to_array(features: Dict[str, float]) -> np.ndarray:
    return np.array([features.get(col, 0.0) for col in FEATURE_COLUMNS]).reshape(1, -1)


def trades_to_training_data(
    trades: List[Dict],
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    """
    Convert closed trade records (with features stored in metadata) to X, y arrays.
    Label: 1 = profitable trade, 0 = losing trade.
    """
    rows = []
    labels = []
    for t in trades:
        meta = t.get("metadata_json") or t.get("metadata") or {}
        feat = meta.get("features", {})
        if not feat:
            continue
        row = [feat.get(col, 0.0) for col in FEATURE_COLUMNS]
        label = 1 if t.get("pnl", 0) > 0 else 0
        rows.append(row)
        labels.append(label)

    if len(rows) < 20:
        return None, None

    return np.array(rows), np.array(labels)
