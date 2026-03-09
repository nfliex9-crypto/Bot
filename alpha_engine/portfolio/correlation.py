"""
Correlation analysis for strategy diversification.

Provides robust correlation estimation, clustering of similar strategies,
and diversification scoring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class CorrelationAnalyzer:
    """Analyze and manage correlation structure of strategy returns."""

    @staticmethod
    def shrunk_correlation(returns_matrix: pd.DataFrame, shrinkage: float = 0.5) -> pd.DataFrame:
        """
        Ledoit-Wolf-style shrinkage of the correlation matrix toward
        the identity matrix to reduce estimation error.
        """
        sample_corr = returns_matrix.corr()
        n = sample_corr.shape[0]
        target = pd.DataFrame(np.eye(n), index=sample_corr.index, columns=sample_corr.columns)
        shrunk = (1 - shrinkage) * sample_corr + shrinkage * target
        return shrunk

    @staticmethod
    def rolling_correlation(
        returns_matrix: pd.DataFrame, window: int = 63,
    ) -> dict[tuple[str, str], pd.Series]:
        """Compute rolling pairwise correlations."""
        cols = returns_matrix.columns.tolist()
        result = {}
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                a, b = cols[i], cols[j]
                result[(a, b)] = returns_matrix[a].rolling(window).corr(returns_matrix[b])
        return result

    @staticmethod
    def cluster_strategies(
        returns_matrix: pd.DataFrame, n_clusters: int = 5,
    ) -> dict[str, int]:
        """
        Cluster strategies by return similarity using hierarchical clustering
        on the correlation distance matrix.
        """
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import squareform

        corr = returns_matrix.corr()
        dist = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist.values, 0)

        condensed = squareform(dist.values, checks=False)
        Z = linkage(condensed, method="ward")
        labels = fcluster(Z, n_clusters, criterion="maxclust")

        return dict(zip(returns_matrix.columns, labels))

    @staticmethod
    def diversification_ratio(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
        """
        Diversification ratio = weighted avg vol / portfolio vol.
        Higher values mean better diversification.
        """
        vols = np.sqrt(np.diag(cov_matrix))
        weighted_vol = weights @ vols
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        return weighted_vol / port_vol if port_vol > 0 else 1.0

    @staticmethod
    def marginal_contribution_to_risk(
        weights: np.ndarray, cov_matrix: np.ndarray,
    ) -> np.ndarray:
        """Compute each strategy's marginal contribution to portfolio risk."""
        port_vol = np.sqrt(weights @ cov_matrix @ weights)
        if port_vol == 0:
            return np.zeros(len(weights))
        mcr = (cov_matrix @ weights) / port_vol
        return weights * mcr
