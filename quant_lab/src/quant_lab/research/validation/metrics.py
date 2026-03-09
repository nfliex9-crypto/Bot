from __future__ import annotations

import numpy as np


def sharpe(returns: np.ndarray, ann_factor: int = 252) -> float:
    mu = float(np.nanmean(returns))
    sd = float(np.nanstd(returns))
    if sd == 0:
        return 0.0
    return (mu / sd) * (ann_factor**0.5)


def sortino(returns: np.ndarray, ann_factor: int = 252) -> float:
    downside = returns[returns < 0]
    dd = float(np.nanstd(downside)) if downside.size else 0.0
    if dd == 0:
        return 0.0
    return (float(np.nanmean(returns)) / dd) * (ann_factor**0.5)


def max_drawdown(equity_curve: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity_curve)
    dd = equity_curve / peaks - 1.0
    return float(np.min(dd))


def profit_factor(returns: np.ndarray) -> float:
    gross_profit = float(np.nansum(returns[returns > 0]))
    gross_loss = abs(float(np.nansum(returns[returns < 0])))
    if gross_loss == 0:
        return 0.0
    return gross_profit / gross_loss
