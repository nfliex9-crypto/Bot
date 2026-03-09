"""
Overfitting Detection.

Methods to detect and measure the degree of overfitting in
backtested strategies, including CSCV (Combinatorially Symmetric
Cross-Validation) and parameter stability analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from ..config import ValidationConfig
from ..strategy.evaluator import StrategyEvaluator

logger = logging.getLogger(__name__)


@dataclass
class OverfitScore:
    """Quantified overfitting assessment."""
    strategy_id: str
    probability_of_overfit: float = 1.0
    parameter_stability_score: float = 0.0
    is_oos_degradation: float = 1.0
    return_consistency: float = 0.0
    regime_robustness: float = 0.0
    overall_score: float = 0.0
    is_overfit: bool = True

    def summary(self) -> dict[str, float]:
        return {
            "probability_of_overfit": self.probability_of_overfit,
            "parameter_stability": self.parameter_stability_score,
            "is_oos_degradation": self.is_oos_degradation,
            "return_consistency": self.return_consistency,
            "regime_robustness": self.regime_robustness,
            "overall_score": self.overall_score,
        }


class OverfitDetector:
    """
    Detects overfitting through multiple orthogonal tests.
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()

    def assess(
        self,
        returns: pd.Series,
        strategy_id: str = "",
        is_sharpe: float = 0.0,
        oos_sharpe: float = 0.0,
    ) -> OverfitScore:
        """Run complete overfitting assessment."""
        score = OverfitScore(strategy_id=strategy_id)

        score.is_oos_degradation = self._is_oos_degradation(is_sharpe, oos_sharpe)
        score.return_consistency = self._return_consistency(returns)
        score.probability_of_overfit = self._cscv_probability(returns)
        score.regime_robustness = self._regime_robustness(returns)

        weights = [0.3, 0.2, 0.3, 0.2]
        components = [
            1 - score.probability_of_overfit,
            1 - score.is_oos_degradation,
            score.return_consistency,
            score.regime_robustness,
        ]
        score.overall_score = sum(w * c for w, c in zip(weights, components))
        score.is_overfit = score.overall_score < 0.5

        return score

    def _is_oos_degradation(self, is_sharpe: float, oos_sharpe: float) -> float:
        """Measure how much performance degrades out-of-sample."""
        if is_sharpe <= 0:
            return 1.0
        degradation = 1 - (oos_sharpe / is_sharpe)
        return max(0, min(1, degradation))

    def _return_consistency(self, returns: pd.Series) -> float:
        """
        Measure consistency of returns across time sub-periods.
        High consistency = less likely overfit.
        """
        n = len(returns)
        n_chunks = 6
        chunk_size = n // n_chunks

        if chunk_size < 20:
            return 0.0

        chunk_sharpes = []
        for i in range(n_chunks):
            chunk = returns.iloc[i * chunk_size:(i + 1) * chunk_size]
            metrics = StrategyEvaluator.evaluate(chunk)
            chunk_sharpes.append(metrics.sharpe_ratio)

        if not chunk_sharpes:
            return 0.0

        positive_pct = sum(1 for s in chunk_sharpes if s > 0) / len(chunk_sharpes)
        cv = np.std(chunk_sharpes) / abs(np.mean(chunk_sharpes)) if np.mean(chunk_sharpes) != 0 else 10
        stability = max(0, 1 - cv / 3)

        return 0.6 * positive_pct + 0.4 * stability

    def _cscv_probability(self, returns: pd.Series, n_splits: int = 8) -> float:
        """
        Combinatorially Symmetric Cross-Validation (CSCV).

        Estimates the probability that the strategy is overfit by
        comparing IS and OOS performance across all possible
        train/test splits of the data.
        """
        n = len(returns)
        chunk_size = n // n_splits
        if chunk_size < 20:
            return 1.0

        chunks = [returns.iloc[i * chunk_size:(i + 1) * chunk_size] for i in range(n_splits)]

        n_underperform = 0
        n_total = 0

        from itertools import combinations
        half = n_splits // 2
        all_combos = list(combinations(range(n_splits), half))

        max_combos = min(len(all_combos), 50)
        rng = np.random.RandomState(42)
        selected = rng.choice(len(all_combos), size=max_combos, replace=False)

        for idx in selected:
            train_indices = set(all_combos[idx])
            test_indices = set(range(n_splits)) - train_indices

            train_rets = pd.concat([chunks[i] for i in sorted(train_indices)])
            test_rets = pd.concat([chunks[i] for i in sorted(test_indices)])

            is_sharpe = StrategyEvaluator.evaluate(train_rets).sharpe_ratio
            oos_sharpe = StrategyEvaluator.evaluate(test_rets).sharpe_ratio

            if is_sharpe > 0 and oos_sharpe < is_sharpe * 0.5:
                n_underperform += 1
            n_total += 1

        return n_underperform / n_total if n_total > 0 else 1.0

    def _regime_robustness(self, returns: pd.Series) -> float:
        """
        Test if strategy works across different volatility regimes.
        """
        vol = returns.rolling(21).std()
        vol_median = vol.median()

        low_vol_returns = returns[vol <= vol_median]
        high_vol_returns = returns[vol > vol_median]

        if len(low_vol_returns) < 30 or len(high_vol_returns) < 30:
            return 0.0

        low_sharpe = StrategyEvaluator.evaluate(low_vol_returns).sharpe_ratio
        high_sharpe = StrategyEvaluator.evaluate(high_vol_returns).sharpe_ratio

        both_positive = float(low_sharpe > 0 and high_sharpe > 0)
        diff = abs(low_sharpe - high_sharpe) / max(abs(low_sharpe), abs(high_sharpe), 0.01)
        balance = max(0, 1 - diff)

        return 0.5 * both_positive + 0.5 * balance
