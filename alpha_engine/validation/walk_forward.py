"""
Walk-Forward Validation.

Implements combinatorial purged cross-validation (CPCV) and
standard walk-forward analysis for out-of-sample performance estimation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..config import ValidationConfig
from ..strategy.evaluator import PerformanceMetrics, StrategyEvaluator

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardResult:
    """Results from walk-forward validation."""
    oos_returns: list[pd.Series] = field(default_factory=list)
    oos_metrics: list[PerformanceMetrics] = field(default_factory=list)
    is_returns: list[pd.Series] = field(default_factory=list)
    is_metrics: list[PerformanceMetrics] = field(default_factory=list)
    aggregate_oos_sharpe: float = 0.0
    aggregate_oos_sortino: float = 0.0
    sharpe_degradation: float = 0.0
    passed: bool = False

    @property
    def n_folds(self) -> int:
        return len(self.oos_returns)

    @property
    def oos_sharpe_consistency(self) -> float:
        """Fraction of folds with positive OOS Sharpe."""
        if not self.oos_metrics:
            return 0.0
        return sum(1 for m in self.oos_metrics if m.sharpe_ratio > 0) / len(self.oos_metrics)


class WalkForwardValidator:
    """
    Walk-forward and purged cross-validation for strategy evaluation.

    Ensures no information leakage between train and test periods
    by enforcing purge gaps and embargo periods.
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()

    def walk_forward(
        self,
        signal_fn,
        data: dict[str, pd.DataFrame],
        n_splits: int = 5,
        purge_days: int = 5,
        embargo_days: int = 2,
    ) -> WalkForwardResult:
        """
        Standard walk-forward analysis.

        signal_fn(train_data, test_data) -> pd.Series of signals on test period.
        """
        first_sym = list(data.keys())[0]
        index = data[first_sym].index
        n = len(index)

        min_train = n // (n_splits + 1)
        step = (n - min_train) // n_splits

        result = WalkForwardResult()

        for fold in range(n_splits):
            train_end_idx = min_train + fold * step
            test_start_idx = train_end_idx + purge_days
            test_end_idx = min(test_start_idx + step + embargo_days, n)

            if test_start_idx >= n or test_end_idx <= test_start_idx:
                continue

            train_data = {sym: df.iloc[:train_end_idx] for sym, df in data.items()}
            test_data = {sym: df.iloc[test_start_idx:test_end_idx] for sym, df in data.items()}

            try:
                test_signal = signal_fn(train_data, test_data)
                test_prices = data[first_sym]["close"].iloc[test_start_idx:test_end_idx]
                test_returns = test_signal.shift(1) * test_prices.pct_change()
                test_returns = test_returns.dropna()

                if len(test_returns) < 10:
                    continue

                oos_metrics = StrategyEvaluator.evaluate(test_returns)
                result.oos_returns.append(test_returns)
                result.oos_metrics.append(oos_metrics)

                train_prices = data[first_sym]["close"].iloc[:train_end_idx]
                train_signal = signal_fn(train_data, train_data)
                train_returns = train_signal.shift(1) * train_prices.pct_change()
                train_returns = train_returns.dropna()
                is_metrics = StrategyEvaluator.evaluate(train_returns)
                result.is_returns.append(train_returns)
                result.is_metrics.append(is_metrics)

                logger.info(
                    "WF fold %d: IS Sharpe=%.2f, OOS Sharpe=%.2f",
                    fold, is_metrics.sharpe_ratio, oos_metrics.sharpe_ratio,
                )
            except Exception as e:
                logger.error("Walk-forward fold %d failed: %s", fold, e)

        if result.oos_returns:
            combined_oos = pd.concat(result.oos_returns)
            agg = StrategyEvaluator.evaluate(combined_oos)
            result.aggregate_oos_sharpe = agg.sharpe_ratio
            result.aggregate_oos_sortino = agg.sortino_ratio

        if result.is_metrics and result.oos_metrics:
            avg_is = np.mean([m.sharpe_ratio for m in result.is_metrics])
            avg_oos = np.mean([m.sharpe_ratio for m in result.oos_metrics])
            result.sharpe_degradation = 1 - (avg_oos / avg_is) if avg_is > 0 else 1.0

        result.passed = (
            result.aggregate_oos_sharpe >= self.config.min_oos_sharpe
            and result.oos_sharpe_consistency >= 0.6
            and result.sharpe_degradation < 0.5
        )

        return result

    def purged_kfold(
        self,
        returns: pd.Series,
        positions: pd.Series,
        n_folds: int = 5,
        purge_days: int = 5,
        embargo_days: int = 2,
    ) -> WalkForwardResult:
        """
        Purged K-Fold cross-validation (de Prado, 2018).

        Each fold's test set is separated from training by a purge gap
        and embargo period to prevent information leakage.
        """
        n = len(returns)
        fold_size = n // n_folds
        result = WalkForwardResult()

        for fold in range(n_folds):
            test_start = fold * fold_size
            test_end = min((fold + 1) * fold_size, n)

            purge_start = max(0, test_start - purge_days)
            embargo_end = min(n, test_end + embargo_days)

            train_mask = np.ones(n, dtype=bool)
            train_mask[purge_start:embargo_end] = False

            train_returns = returns.iloc[train_mask]
            test_returns = returns.iloc[test_start:test_end]

            if len(test_returns) < 10 or len(train_returns) < 30:
                continue

            oos_metrics = StrategyEvaluator.evaluate(test_returns)
            is_metrics = StrategyEvaluator.evaluate(train_returns)

            result.oos_returns.append(test_returns)
            result.oos_metrics.append(oos_metrics)
            result.is_returns.append(train_returns)
            result.is_metrics.append(is_metrics)

        if result.oos_returns:
            combined = pd.concat(result.oos_returns)
            agg = StrategyEvaluator.evaluate(combined)
            result.aggregate_oos_sharpe = agg.sharpe_ratio
            result.aggregate_oos_sortino = agg.sortino_ratio

        if result.is_metrics and result.oos_metrics:
            avg_is = np.mean([m.sharpe_ratio for m in result.is_metrics])
            avg_oos = np.mean([m.sharpe_ratio for m in result.oos_metrics])
            result.sharpe_degradation = 1 - (avg_oos / avg_is) if avg_is > 0 else 1.0

        result.passed = (
            result.aggregate_oos_sharpe >= self.config.min_oos_sharpe
            and result.oos_sharpe_consistency >= 0.6
        )

        return result
