"""
Statistical Validation Engine.

Rigorous statistical tests for strategy significance including
deflated Sharpe ratio, multiple testing corrections, and
distribution-based hypothesis testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from ..config import ValidationConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of statistical validation for a single strategy."""
    strategy_id: str
    passed: bool
    sharpe_pvalue: float = 1.0
    deflated_sharpe: float = 0.0
    deflated_sharpe_pvalue: float = 1.0
    is_oos_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    profit_factor_pvalue: float = 1.0
    stationarity_pvalue: float = 1.0
    is_stationary: bool = False
    notes: list[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


class StatisticalValidator:
    """
    Applies rigorous statistical tests to separate genuine alpha
    from overfitted noise.
    """

    def __init__(self, config: Optional[ValidationConfig] = None) -> None:
        self.config = config or ValidationConfig()

    def validate(
        self,
        returns: pd.Series,
        strategy_id: str = "",
        n_strategies_tested: int = 1,
    ) -> ValidationResult:
        """Run the full validation battery on a strategy's returns."""
        result = ValidationResult(strategy_id=strategy_id, passed=False)

        if len(returns) < self.config.min_trades:
            result.notes.append(f"Insufficient data: {len(returns)} < {self.config.min_trades}")
            return result

        sharpe = self._annualized_sharpe(returns)
        result.sharpe_pvalue = self._sharpe_pvalue(returns, sharpe)

        result.deflated_sharpe = self._deflated_sharpe_ratio(
            sharpe, returns, n_strategies_tested,
        )
        result.deflated_sharpe_pvalue = self._sharpe_pvalue(
            returns, result.deflated_sharpe,
        )

        result.stationarity_pvalue = self._stationarity_test(returns)
        result.is_stationary = result.stationarity_pvalue < 0.05

        oos_start = int(len(returns) * (1 - self.config.oos_ratio))
        oos_returns = returns.iloc[oos_start:]
        result.oos_sharpe = self._annualized_sharpe(oos_returns)
        result.is_oos_sharpe = result.oos_sharpe

        result.profit_factor_pvalue = self._profit_factor_significance(returns)

        passed_checks = [
            sharpe >= self.config.min_sharpe,
            result.oos_sharpe >= self.config.min_oos_sharpe,
            result.deflated_sharpe_pvalue <= self.config.deflated_sharpe_threshold,
            result.stationarity_pvalue < 0.10,
        ]

        if sharpe < self.config.min_sharpe:
            result.notes.append(f"Sharpe {sharpe:.2f} < min {self.config.min_sharpe}")
        if result.oos_sharpe < self.config.min_oos_sharpe:
            result.notes.append(f"OOS Sharpe {result.oos_sharpe:.2f} < min {self.config.min_oos_sharpe}")
        if result.deflated_sharpe_pvalue > self.config.deflated_sharpe_threshold:
            result.notes.append(f"Deflated Sharpe p-value {result.deflated_sharpe_pvalue:.3f} too high")

        result.passed = sum(passed_checks) >= 3
        return result

    def _annualized_sharpe(self, returns: pd.Series) -> float:
        if returns.std() == 0:
            return 0.0
        return returns.mean() / returns.std() * np.sqrt(252)

    def _sharpe_pvalue(self, returns: pd.Series, sharpe: float) -> float:
        """
        Hypothesis test: H0: true Sharpe <= 0.
        Uses the Jobson-Korkie standard error.
        """
        n = len(returns)
        if n < 10:
            return 1.0
        se = np.sqrt((1 + 0.5 * sharpe**2 - returns.skew() * sharpe +
                      (returns.kurt() / 4) * sharpe**2) / n)
        if se <= 0:
            return 1.0
        z = sharpe / se
        return 1 - sp_stats.norm.cdf(z)

    def _deflated_sharpe_ratio(
        self,
        observed_sharpe: float,
        returns: pd.Series,
        n_trials: int,
    ) -> float:
        """
        Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio.
        Adjusts for multiple testing by penalizing based on the
        expected maximum Sharpe from n_trials of noise.
        """
        if n_trials <= 1:
            return observed_sharpe

        n = len(returns)
        skew = returns.skew()
        kurt = returns.kurt()

        e_max_sharpe = self._expected_max_sharpe(n_trials, n)

        se = np.sqrt((1 - skew * observed_sharpe +
                      (kurt - 1) / 4 * observed_sharpe**2) / (n - 1))
        if se <= 0:
            return 0.0

        dsr = (observed_sharpe - e_max_sharpe) / se
        return dsr

    @staticmethod
    def _expected_max_sharpe(n_trials: int, n_obs: int) -> float:
        """Expected maximum Sharpe under null of n independent strategies."""
        from scipy.special import erfinv
        if n_trials <= 1:
            return 0.0
        euler_mascheroni = 0.5772156649
        z = (1 - euler_mascheroni) * sp_stats.norm.ppf(1 - 1 / n_trials) + \
            euler_mascheroni * sp_stats.norm.ppf(1 - 1 / (n_trials * np.e))
        return z * (1 / np.sqrt(n_obs)) * np.sqrt(252)

    @staticmethod
    def _stationarity_test(returns: pd.Series) -> float:
        """Augmented Dickey-Fuller test for return stationarity."""
        from statsmodels.tsa.stattools import adfuller
        try:
            result = adfuller(returns.dropna(), maxlag=10, autolag="AIC")
            return result[1]
        except Exception:
            return 1.0

    @staticmethod
    def _profit_factor_significance(returns: pd.Series) -> float:
        """Bootstrap test for profit factor > 1."""
        wins = returns[returns > 0].sum()
        losses = abs(returns[returns < 0].sum())
        if losses == 0:
            return 0.0

        pf = wins / losses
        n_boot = 1000
        rng = np.random.RandomState(42)
        pf_boot = []
        for _ in range(n_boot):
            sample = rng.choice(returns.values, size=len(returns), replace=True)
            w = sample[sample > 0].sum()
            l = abs(sample[sample < 0].sum())
            pf_boot.append(w / l if l > 0 else 0)

        return np.mean(np.array(pf_boot) >= pf)
