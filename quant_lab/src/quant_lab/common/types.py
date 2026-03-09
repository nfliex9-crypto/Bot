from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyThresholds:
    sharpe_min: float
    max_drawdown_min: float
    profit_factor_min: float
