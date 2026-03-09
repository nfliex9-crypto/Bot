"""
Backtest result container with analysis and visualization utilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ..strategy.evaluator import PerformanceMetrics, StrategyEvaluator


@dataclass
class BacktestResult:
    """Complete backtest output for a single strategy."""
    strategy_id: str = ""
    strategy_name: str = ""
    returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    positions: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    costs: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    gross_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    metrics: Optional[PerformanceMetrics] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_metrics(self, risk_free_rate: float = 0.0) -> PerformanceMetrics:
        self.metrics = StrategyEvaluator.evaluate(
            self.returns, self.positions, risk_free_rate,
        )
        return self.metrics

    @property
    def sharpe(self) -> float:
        if self.metrics is None:
            self.compute_metrics()
        return self.metrics.sharpe_ratio

    @property
    def max_drawdown(self) -> float:
        if self.metrics is None:
            self.compute_metrics()
        return self.metrics.max_drawdown

    def drawdown_series(self) -> pd.Series:
        return StrategyEvaluator.drawdown_series(self.returns)

    def rolling_sharpe(self, window: int = 63) -> pd.Series:
        return StrategyEvaluator.rolling_sharpe(self.returns, window)

    def monthly_returns(self) -> pd.Series:
        if isinstance(self.returns.index, pd.DatetimeIndex):
            return self.returns.groupby(pd.Grouper(freq="ME")).sum()
        return self.returns

    def annual_returns(self) -> pd.Series:
        if isinstance(self.returns.index, pd.DatetimeIndex):
            return self.returns.groupby(pd.Grouper(freq="YE")).sum()
        return self.returns

    def summary(self) -> dict[str, Any]:
        if self.metrics is None:
            self.compute_metrics()
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "total_bars": len(self.returns),
            "total_cost": self.costs.sum() if not self.costs.empty else 0,
            **self.metrics.to_dict(),
        }
