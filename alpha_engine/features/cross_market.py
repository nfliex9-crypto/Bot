"""
Cross-market relationship features.

Captures lead-lag dynamics, correlation regimes, relative strength,
and inter-market divergences used for cross-asset alpha generation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class CrossMarketFeatures:
    """Generate features capturing cross-asset relationships."""

    @staticmethod
    def rolling_correlation(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
        return a.rolling(window).corr(b)

    @staticmethod
    def correlation_change(a: pd.Series, b: pd.Series, short: int, long: int) -> pd.Series:
        """Detect correlation regime shifts."""
        short_corr = a.rolling(short).corr(b)
        long_corr = a.rolling(long).corr(b)
        return short_corr - long_corr

    @staticmethod
    def lead_lag_correlation(
        leader: pd.Series, follower: pd.Series, max_lag: int, window: int,
    ) -> pd.DataFrame:
        """Compute rolling cross-correlation at multiple lags."""
        results = {}
        for lag in range(-max_lag, max_lag + 1):
            shifted = leader.shift(lag)
            results[f"xcorr_lag_{lag}"] = follower.rolling(window).corr(shifted)
        return pd.DataFrame(results)

    @staticmethod
    def relative_strength(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
        """Rolling ratio of cumulative returns — classic pair-trading signal."""
        ra = a.pct_change().rolling(window).sum()
        rb = b.pct_change().rolling(window).sum()
        return ra - rb

    @staticmethod
    def spread_zscore(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
        """Z-score of the price spread — mean-reversion signal."""
        spread = np.log(a) - np.log(b)
        mean = spread.rolling(window).mean()
        std = spread.rolling(window).std()
        return (spread - mean) / std.replace(0, np.nan)

    @staticmethod
    def cointegration_residual(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
        """Rolling OLS hedge ratio residual for cointegration-based signals."""
        def _resid(ab: np.ndarray) -> float:
            n = len(ab) // 2
            x, y = ab[:n], ab[n:]
            if np.std(x) == 0:
                return np.nan
            beta = np.cov(x, y)[0, 1] / np.var(x)
            return y[-1] - beta * x[-1]

        combined = pd.concat([b.rename("x"), a.rename("y")], axis=1).dropna()
        stacked = pd.concat([combined["x"], combined["y"]])
        return pd.Series(
            [_resid(np.concatenate([
                combined["x"].iloc[max(0, i - window):i].values,
                combined["y"].iloc[max(0, i - window):i].values,
            ])) if i >= window else np.nan for i in range(len(combined))],
            index=combined.index,
        )

    @staticmethod
    def sector_momentum(returns_matrix: pd.DataFrame, window: int) -> pd.DataFrame:
        """Cross-sectional momentum scores for all assets."""
        cum_ret = returns_matrix.rolling(window).sum()
        cross_mean = cum_ret.mean(axis=1)
        cross_std = cum_ret.std(axis=1)
        return cum_ret.sub(cross_mean, axis=0).div(cross_std.replace(0, np.nan), axis=0)

    @staticmethod
    def dispersion(returns_matrix: pd.DataFrame, window: int) -> pd.Series:
        """Cross-sectional return dispersion — high values signal regime uncertainty."""
        return returns_matrix.rolling(window).std().mean(axis=1)

    @staticmethod
    def beta_matrix(
        returns_matrix: pd.DataFrame, market_returns: pd.Series, window: int,
    ) -> pd.DataFrame:
        """Rolling betas of all assets vs. the market."""
        betas = {}
        for col in returns_matrix.columns:
            cov = returns_matrix[col].rolling(window).cov(market_returns)
            var = market_returns.rolling(window).var()
            betas[col] = cov / var.replace(0, np.nan)
        return pd.DataFrame(betas)

    @staticmethod
    def pca_factor_loadings(returns_matrix: pd.DataFrame, window: int, n_components: int = 3) -> pd.DataFrame:
        """Rolling PCA factor loadings — extracts latent systematic factors."""
        from sklearn.decomposition import PCA

        loadings_list = []
        index_out = []

        for i in range(window, len(returns_matrix)):
            chunk = returns_matrix.iloc[i - window:i].dropna(axis=1)
            if chunk.shape[1] < n_components or chunk.shape[0] < n_components:
                continue
            pca = PCA(n_components=n_components)
            pca.fit(chunk.values)
            row = {}
            for j in range(n_components):
                row[f"pca_var_ratio_{j}"] = pca.explained_variance_ratio_[j]
            loadings_list.append(row)
            index_out.append(returns_matrix.index[i])

        return pd.DataFrame(loadings_list, index=index_out)
