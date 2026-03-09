"""
Capital allocation models for multi-strategy portfolios.

Implements several institutional allocation frameworks including
risk parity, inverse volatility, Kelly criterion, and
equal risk contribution.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CapitalAllocator:
    """Allocate capital across selected strategies."""

    @staticmethod
    def equal_weight(n_strategies: int) -> np.ndarray:
        return np.ones(n_strategies) / n_strategies

    @staticmethod
    def inverse_volatility(volatilities: np.ndarray) -> np.ndarray:
        """Weight inversely proportional to realized volatility."""
        inv_vol = 1.0 / np.maximum(volatilities, 1e-10)
        return inv_vol / inv_vol.sum()

    @staticmethod
    def risk_parity(cov_matrix: np.ndarray, max_iter: int = 1000, tol: float = 1e-8) -> np.ndarray:
        """
        Equal risk contribution portfolio.
        Each strategy contributes equally to total portfolio variance.
        """
        n = cov_matrix.shape[0]
        w = np.ones(n) / n

        for _ in range(max_iter):
            port_var = w @ cov_matrix @ w
            if port_var <= 0:
                break
            marginal = cov_matrix @ w
            risk_contrib = w * marginal

            target = port_var / n
            w_new = w * (target / np.maximum(risk_contrib, 1e-10))
            w_new = w_new / w_new.sum()

            if np.max(np.abs(w_new - w)) < tol:
                break
            w = w_new

        return w

    @staticmethod
    def kelly_criterion(
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        fraction: float = 0.5,
    ) -> np.ndarray:
        """
        Fractional Kelly allocation.

        Full Kelly maximizes geometric growth but is too aggressive;
        fraction < 1 provides a more conservative allocation.
        """
        try:
            cov_inv = np.linalg.inv(cov_matrix)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov_matrix)

        raw_weights = cov_inv @ expected_returns
        raw_weights *= fraction

        raw_weights = raw_weights / np.abs(raw_weights).sum()
        return raw_weights

    @staticmethod
    def max_sharpe(
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_free: float = 0.0,
    ) -> np.ndarray:
        """Analytical maximum Sharpe ratio portfolio (Markowitz tangency)."""
        excess = expected_returns - risk_free
        try:
            cov_inv = np.linalg.inv(cov_matrix)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov_matrix)

        raw = cov_inv @ excess
        raw = raw / raw.sum()
        return raw

    @staticmethod
    def min_variance(cov_matrix: np.ndarray) -> np.ndarray:
        """Global minimum variance portfolio."""
        n = cov_matrix.shape[0]
        try:
            cov_inv = np.linalg.inv(cov_matrix)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov_matrix)

        ones = np.ones(n)
        raw = cov_inv @ ones
        return raw / raw.sum()

    @staticmethod
    def hierarchical_risk_parity(returns_matrix: pd.DataFrame) -> np.ndarray:
        """
        Hierarchical Risk Parity (Lopez de Prado, 2016).

        Uses hierarchical clustering on the correlation structure
        to produce a robust allocation.
        """
        from scipy.cluster.hierarchy import leaves_list, linkage
        from scipy.spatial.distance import squareform

        corr = returns_matrix.corr()
        dist = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist.values, 0)

        condensed = squareform(dist.values, checks=False)
        Z = linkage(condensed, method="single")
        sort_idx = leaves_list(Z).tolist()

        cov = returns_matrix.cov().values
        n = len(sort_idx)
        weights = np.ones(n)

        def _bisect(items: list[int]) -> None:
            if len(items) <= 1:
                return
            mid = len(items) // 2
            left = items[:mid]
            right = items[mid:]

            var_left = _cluster_variance(cov, left)
            var_right = _cluster_variance(cov, right)
            alpha = 1 - var_left / (var_left + var_right) if (var_left + var_right) > 0 else 0.5

            for i in left:
                weights[i] *= alpha
            for i in right:
                weights[i] *= (1 - alpha)

            _bisect(left)
            _bisect(right)

        def _cluster_variance(cov_mat: np.ndarray, indices: list[int]) -> float:
            sub_cov = cov_mat[np.ix_(indices, indices)]
            inv_diag = 1.0 / np.diag(sub_cov)
            w = inv_diag / inv_diag.sum()
            return w @ sub_cov @ w

        _bisect(sort_idx)

        reordered = np.zeros(n)
        for new_pos, orig_idx in enumerate(sort_idx):
            reordered[orig_idx] = weights[new_pos]

        return reordered / reordered.sum()
