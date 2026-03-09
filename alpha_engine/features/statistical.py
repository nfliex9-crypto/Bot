"""
Statistical feature transformations for alpha factor generation.

Generates z-scores, rank transforms, autoregressive features,
rolling statistics, and distributional metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sp_stats


class StatisticalFeatures:
    """Generate statistical alpha factors from price and volume data."""

    @staticmethod
    def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
        mean = series.rolling(window).mean()
        std = series.rolling(window).std()
        return (series - mean) / std.replace(0, np.nan)

    @staticmethod
    def rolling_rank(series: pd.Series, window: int) -> pd.Series:
        """Percentile rank of current value within rolling window."""
        def _rank(x: np.ndarray) -> float:
            if len(x) < 2 or np.isnan(x[-1]):
                return np.nan
            return sp_stats.percentileofscore(x[:-1], x[-1]) / 100.0
        return series.rolling(window + 1).apply(_rank, raw=True)

    @staticmethod
    def log_returns(close: pd.Series) -> pd.Series:
        return np.log(close / close.shift(1))

    @staticmethod
    def momentum(close: pd.Series, period: int) -> pd.Series:
        return close.pct_change(period)

    @staticmethod
    def rate_of_change(close: pd.Series, period: int) -> pd.Series:
        return (close - close.shift(period)) / close.shift(period)

    @staticmethod
    def rolling_skew(returns: pd.Series, window: int) -> pd.Series:
        return returns.rolling(window).skew()

    @staticmethod
    def rolling_kurtosis(returns: pd.Series, window: int) -> pd.Series:
        return returns.rolling(window).kurt()

    @staticmethod
    def hurst_exponent(series: pd.Series, window: int = 100) -> pd.Series:
        """Rolling Hurst exponent — measures mean-reversion vs trending."""
        def _hurst(x: np.ndarray) -> float:
            if len(x) < 20:
                return np.nan
            lags = range(2, min(len(x) // 2, 20))
            tau = [np.std(np.subtract(x[lag:], x[:-lag])) for lag in lags]
            if any(t == 0 for t in tau):
                return np.nan
            log_lags = np.log(list(lags))
            log_tau = np.log(tau)
            slope, _, _, _, _ = sp_stats.linregress(log_lags, log_tau)
            return slope
        return series.rolling(window).apply(_hurst, raw=True)

    @staticmethod
    def autocorrelation(returns: pd.Series, lag: int, window: int) -> pd.Series:
        return returns.rolling(window).apply(
            lambda x: pd.Series(x).autocorr(lag=lag) if len(x) > lag else np.nan,
            raw=True,
        )

    @staticmethod
    def rolling_beta(asset_returns: pd.Series, market_returns: pd.Series, window: int) -> pd.Series:
        """Rolling beta relative to a market benchmark."""
        cov = asset_returns.rolling(window).cov(market_returns)
        var = market_returns.rolling(window).var()
        return cov / var.replace(0, np.nan)

    @staticmethod
    def information_ratio(returns: pd.Series, benchmark: pd.Series, window: int) -> pd.Series:
        excess = returns - benchmark
        return excess.rolling(window).mean() / excess.rolling(window).std().replace(0, np.nan)

    @staticmethod
    def lagged_features(series: pd.Series, max_lag: int) -> pd.DataFrame:
        """Generate lagged versions of a series."""
        return pd.DataFrame(
            {f"lag_{i}": series.shift(i) for i in range(1, max_lag + 1)}
        )

    @staticmethod
    def rolling_quantile(series: pd.Series, window: int, quantile: float) -> pd.Series:
        return series.rolling(window).quantile(quantile)

    @staticmethod
    def rolling_entropy(series: pd.Series, window: int, n_bins: int = 10) -> pd.Series:
        """Rolling Shannon entropy of the distribution."""
        def _entropy(x: np.ndarray) -> float:
            counts, _ = np.histogram(x, bins=n_bins)
            probs = counts / counts.sum()
            probs = probs[probs > 0]
            return -np.sum(probs * np.log2(probs))
        return series.rolling(window).apply(_entropy, raw=True)
