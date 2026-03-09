"""
Monte Carlo Simulation for Strategy Validation.

Tests strategy robustness by simulating alternative return paths
and measuring the distribution of key metrics across scenarios.
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
class MonteCarloResult:
    """Distribution of performance metrics across Monte Carlo scenarios."""
    n_simulations: int = 0
    sharpe_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    max_dd_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    total_return_distribution: np.ndarray = field(default_factory=lambda: np.array([]))
    sortino_distribution: np.ndarray = field(default_factory=lambda: np.array([]))

    sharpe_mean: float = 0.0
    sharpe_5th_pctile: float = 0.0
    sharpe_95th_pctile: float = 0.0
    max_dd_mean: float = 0.0
    max_dd_95th_pctile: float = 0.0
    prob_positive_sharpe: float = 0.0
    prob_profit: float = 0.0
    passed: bool = False

    def summary(self) -> dict[str, float]:
        return {
            "n_simulations": self.n_simulations,
            "sharpe_mean": self.sharpe_mean,
            "sharpe_5th": self.sharpe_5th_pctile,
            "sharpe_95th": self.sharpe_95th_pctile,
            "max_dd_mean": self.max_dd_mean,
            "max_dd_95th": self.max_dd_95th_pctile,
            "prob_positive_sharpe": self.prob_positive_sharpe,
            "prob_profit": self.prob_profit,
        }


class MonteCarloValidator:
    """
    Monte Carlo simulation engine for strategy robustness testing.

    Implements multiple simulation methods:
    1. Bootstrap resampling of daily returns
    2. Block bootstrap (preserves autocorrelation)
    3. Permutation testing (null hypothesis)
    4. Path simulation (parametric GBM)
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()

    def bootstrap_test(
        self,
        returns: pd.Series,
        n_sims: int = 1000,
        block_size: int = 1,
        seed: int = 42,
    ) -> MonteCarloResult:
        """
        Bootstrap resampling — tests if strategy performance is statistically
        distinguishable from random sampling of actual returns.

        block_size > 1 enables block bootstrap to preserve serial correlation.
        """
        rng = np.random.RandomState(seed)
        n = len(returns)
        values = returns.values

        sharpes = []
        max_dds = []
        total_rets = []
        sortinos = []

        for _ in range(n_sims):
            if block_size == 1:
                sample_idx = rng.randint(0, n, size=n)
            else:
                n_blocks = n // block_size + 1
                block_starts = rng.randint(0, n - block_size + 1, size=n_blocks)
                sample_idx = np.concatenate(
                    [np.arange(s, s + block_size) for s in block_starts]
                )[:n]

            sample = values[sample_idx]
            sample_series = pd.Series(sample)

            metrics = StrategyEvaluator.evaluate(sample_series)
            sharpes.append(metrics.sharpe_ratio)
            max_dds.append(metrics.max_drawdown)
            total_rets.append(metrics.total_return)
            sortinos.append(metrics.sortino_ratio)

        sharpes = np.array(sharpes)
        max_dds = np.array(max_dds)
        total_rets = np.array(total_rets)
        sortinos = np.array(sortinos)

        result = MonteCarloResult(
            n_simulations=n_sims,
            sharpe_distribution=sharpes,
            max_dd_distribution=max_dds,
            total_return_distribution=total_rets,
            sortino_distribution=sortinos,
            sharpe_mean=sharpes.mean(),
            sharpe_5th_pctile=np.percentile(sharpes, 5),
            sharpe_95th_pctile=np.percentile(sharpes, 95),
            max_dd_mean=max_dds.mean(),
            max_dd_95th_pctile=np.percentile(max_dds, 95),
            prob_positive_sharpe=(sharpes > 0).mean(),
            prob_profit=(total_rets > 0).mean(),
        )

        result.passed = (
            result.sharpe_5th_pctile > 0
            and result.prob_positive_sharpe >= self.config.confidence_level
            and result.max_dd_95th_pctile <= self.config.max_drawdown
        )
        return result

    def permutation_test(
        self,
        returns: pd.Series,
        positions: pd.Series,
        n_sims: int = 1000,
        seed: int = 42,
    ) -> float:
        """
        Permutation test: measures the probability that observed Sharpe
        could have been achieved by random timing.

        Returns p-value (lower is better).
        """
        rng = np.random.RandomState(seed)
        observed_metrics = StrategyEvaluator.evaluate(returns)
        observed_sharpe = observed_metrics.sharpe_ratio

        asset_returns = returns / positions.shift(1).replace(0, np.nan)
        asset_returns = asset_returns.dropna()

        better_count = 0
        for _ in range(n_sims):
            shuffled_positions = positions.sample(frac=1, random_state=rng.randint(1e9))
            shuffled_positions.index = positions.index
            sim_returns = shuffled_positions.shift(1) * asset_returns.reindex(positions.index)
            sim_returns = sim_returns.dropna()

            if len(sim_returns) < 20:
                continue

            sim_sharpe = StrategyEvaluator.evaluate(sim_returns).sharpe_ratio
            if sim_sharpe >= observed_sharpe:
                better_count += 1

        return better_count / n_sims

    def path_simulation(
        self,
        returns: pd.Series,
        n_sims: int = 1000,
        seed: int = 42,
    ) -> MonteCarloResult:
        """
        Parametric path simulation using fitted GBM with GARCH-like
        volatility clustering.
        """
        rng = np.random.RandomState(seed)
        n = len(returns)
        mu = returns.mean()
        sigma = returns.std()
        skew = returns.skew()
        kurt = returns.kurt()

        sharpes = []
        max_dds = []
        total_rets = []

        for _ in range(n_sims):
            noise = rng.standard_t(df=max(3, 6 - kurt / 2), size=n)
            noise = noise * sigma + mu

            vol = np.ones(n) * sigma
            alpha, beta = 0.1, 0.85
            for t in range(1, n):
                vol[t] = np.sqrt(alpha * noise[t - 1]**2 + beta * vol[t - 1]**2)
            sim = noise * vol / sigma

            sim_series = pd.Series(sim)
            metrics = StrategyEvaluator.evaluate(sim_series)
            sharpes.append(metrics.sharpe_ratio)
            max_dds.append(metrics.max_drawdown)
            total_rets.append(metrics.total_return)

        sharpes = np.array(sharpes)
        max_dds = np.array(max_dds)
        total_rets = np.array(total_rets)

        return MonteCarloResult(
            n_simulations=n_sims,
            sharpe_distribution=sharpes,
            max_dd_distribution=max_dds,
            total_return_distribution=total_rets,
            sharpe_mean=sharpes.mean(),
            sharpe_5th_pctile=np.percentile(sharpes, 5),
            sharpe_95th_pctile=np.percentile(sharpes, 95),
            max_dd_mean=max_dds.mean(),
            max_dd_95th_pctile=np.percentile(max_dds, 95),
            prob_positive_sharpe=(sharpes > 0).mean(),
            prob_profit=(total_rets > 0).mean(),
            passed=(np.percentile(sharpes, 5) > 0),
        )
