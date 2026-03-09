"""
Portfolio Construction Optimizer.

Combines multiple validated strategies into an optimal portfolio
with diversification constraints, leverage limits, and
volatility targeting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..backtest.results import BacktestResult
from ..config import PortfolioConfig
from ..strategy.evaluator import StrategyEvaluator
from .allocation import CapitalAllocator
from .correlation import CorrelationAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class PortfolioResult:
    """Complete portfolio construction output."""
    weights: dict[str, float] = field(default_factory=dict)
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    expected_sharpe: float = 0.0
    diversification_ratio: float = 0.0
    effective_n_strategies: float = 0.0
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    risk_contributions: dict[str, float] = field(default_factory=dict)
    combined_returns: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    combined_metrics: Optional[dict] = None

    def summary(self) -> dict:
        return {
            "n_strategies": len(self.weights),
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "expected_sharpe": self.expected_sharpe,
            "diversification_ratio": self.diversification_ratio,
            "gross_leverage": self.gross_leverage,
            "net_leverage": self.net_leverage,
            "weights": self.weights,
        }


class PortfolioOptimizer:
    """
    Constructs optimal multi-strategy portfolios with institutional constraints.
    """

    def __init__(self, config: Optional[PortfolioConfig] = None) -> None:
        self.config = config or PortfolioConfig()
        self.allocator = CapitalAllocator()
        self.corr_analyzer = CorrelationAnalyzer()

    def optimize(
        self,
        results: list[BacktestResult],
        method: Optional[str] = None,
    ) -> PortfolioResult:
        """
        Build optimal portfolio from backtested strategies.

        Methods: risk_parity, inverse_vol, max_sharpe, min_variance,
                 hrp (hierarchical risk parity), kelly, equal_weight
        """
        method = method or self.config.optimization_method
        if not results:
            return PortfolioResult()

        returns_matrix = pd.DataFrame(
            {r.strategy_id: r.returns for r in results}
        ).fillna(0)

        cov = returns_matrix.cov().values
        shrunk_corr = self.corr_analyzer.shrunk_correlation(
            returns_matrix, self.config.correlation_shrinkage,
        )
        vols = returns_matrix.std().values
        shrunk_cov = np.outer(vols, vols) * shrunk_corr.values

        expected_rets = returns_matrix.mean().values * 252

        raw_weights = self._compute_weights(
            method, expected_rets, shrunk_cov, returns_matrix,
        )

        constrained = self._apply_constraints(raw_weights, returns_matrix.columns.tolist())

        constrained = self._volatility_target(constrained, shrunk_cov)

        portfolio_result = self._build_result(
            constrained, returns_matrix, shrunk_cov, results,
        )

        logger.info(
            "Portfolio: %d strategies, Sharpe=%.2f, Vol=%.1f%%, Div=%.2f",
            len(portfolio_result.weights),
            portfolio_result.expected_sharpe,
            portfolio_result.expected_volatility * 100,
            portfolio_result.diversification_ratio,
        )

        return portfolio_result

    def _compute_weights(
        self,
        method: str,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        returns_matrix: pd.DataFrame,
    ) -> np.ndarray:
        if method == "risk_parity":
            return self.allocator.risk_parity(cov_matrix)
        elif method == "inverse_vol":
            vols = np.sqrt(np.diag(cov_matrix))
            return self.allocator.inverse_volatility(vols)
        elif method == "max_sharpe":
            return self.allocator.max_sharpe(expected_returns, cov_matrix)
        elif method == "min_variance":
            return self.allocator.min_variance(cov_matrix)
        elif method == "hrp":
            return self.allocator.hierarchical_risk_parity(returns_matrix)
        elif method == "kelly":
            return self.allocator.kelly_criterion(expected_returns, cov_matrix, fraction=0.5)
        else:
            return self.allocator.equal_weight(len(expected_returns))

    def _apply_constraints(self, weights: np.ndarray, strategy_ids: list[str]) -> np.ndarray:
        """Apply portfolio weight constraints."""
        w = weights.copy()

        w = np.clip(w, -self.config.max_single_strategy_weight, self.config.max_single_strategy_weight)

        small_mask = np.abs(w) < self.config.min_strategy_weight
        w[small_mask] = 0.0

        gross = np.abs(w).sum()
        if gross > self.config.max_gross_leverage:
            w = w * self.config.max_gross_leverage / gross

        net = w.sum()
        if abs(net) > self.config.max_net_leverage:
            w = w * self.config.max_net_leverage / abs(net)

        return w

    def _volatility_target(self, weights: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """Scale portfolio to target volatility."""
        port_vol = np.sqrt(weights @ cov_matrix @ weights * 252)
        if port_vol > 0:
            scale = self.config.target_volatility / port_vol
            weights = weights * scale

        gross = np.abs(weights).sum()
        if gross > self.config.max_gross_leverage:
            weights = weights * self.config.max_gross_leverage / gross

        return weights

    def _build_result(
        self,
        weights: np.ndarray,
        returns_matrix: pd.DataFrame,
        cov_matrix: np.ndarray,
        results: list[BacktestResult],
    ) -> PortfolioResult:
        weight_dict = {
            sid: w for sid, w in zip(returns_matrix.columns, weights) if abs(w) > 1e-6
        }

        combined = (returns_matrix * weights).sum(axis=1)
        combined_metrics = StrategyEvaluator.evaluate(combined)

        div_ratio = self.corr_analyzer.diversification_ratio(weights, cov_matrix * 252)
        mcr = self.corr_analyzer.marginal_contribution_to_risk(weights, cov_matrix * 252)
        risk_contrib = {
            sid: r for sid, r in zip(returns_matrix.columns, mcr) if abs(r) > 1e-8
        }

        eff_n = 1.0 / (weights**2).sum() if (weights**2).sum() > 0 else 0

        return PortfolioResult(
            weights=weight_dict,
            expected_return=combined_metrics.annualized_return,
            expected_volatility=combined_metrics.annualized_volatility,
            expected_sharpe=combined_metrics.sharpe_ratio,
            diversification_ratio=div_ratio,
            effective_n_strategies=eff_n,
            gross_leverage=np.abs(weights).sum(),
            net_leverage=weights.sum(),
            risk_contributions=risk_contrib,
            combined_returns=combined,
            combined_metrics=combined_metrics.to_dict(),
        )
