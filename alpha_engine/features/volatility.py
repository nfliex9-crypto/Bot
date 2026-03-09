"""
Volatility feature generators.

Parkinson, Garman-Klass, Yang-Zhang estimators, GARCH-style features,
and volatility regime classification.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class VolatilityFeatures:
    """Generate volatility-based alpha factors from OHLCV data."""

    @staticmethod
    def realized_volatility(returns: pd.Series, window: int) -> pd.Series:
        return returns.rolling(window).std() * np.sqrt(252)

    @staticmethod
    def parkinson_volatility(high: pd.Series, low: pd.Series, window: int) -> pd.Series:
        """Parkinson high-low range estimator — more efficient than close-close."""
        hl_ratio = np.log(high / low) ** 2
        return np.sqrt(hl_ratio.rolling(window).mean() / (4 * np.log(2))) * np.sqrt(252)

    @staticmethod
    def garman_klass_volatility(
        open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int,
    ) -> pd.Series:
        """Garman-Klass estimator using OHLC — most efficient classical estimator."""
        hl = 0.5 * (np.log(high / low)) ** 2
        co = -(2 * np.log(2) - 1) * (np.log(close / open_)) ** 2
        return np.sqrt((hl + co).rolling(window).mean() * 252)

    @staticmethod
    def yang_zhang_volatility(
        open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int,
    ) -> pd.Series:
        """Yang-Zhang estimator — handles overnight jumps."""
        log_oc = np.log(open_ / close.shift(1))
        log_co = np.log(close / open_)
        log_ho = np.log(high / open_)
        log_lo = np.log(low / open_)

        rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)

        overnight_var = log_oc.rolling(window).var()
        close_var = log_co.rolling(window).var()
        rs_var = rs.rolling(window).mean()

        k = 0.34 / (1.34 + (window + 1) / (window - 1))
        return np.sqrt((overnight_var + k * close_var + (1 - k) * rs_var) * 252)

    @staticmethod
    def volatility_ratio(returns: pd.Series, short_window: int, long_window: int) -> pd.Series:
        """Ratio of short-term to long-term volatility — detects regime changes."""
        short_vol = returns.rolling(short_window).std()
        long_vol = returns.rolling(long_window).std()
        return short_vol / long_vol.replace(0, np.nan)

    @staticmethod
    def volatility_of_volatility(returns: pd.Series, vol_window: int, vov_window: int) -> pd.Series:
        vol = returns.rolling(vol_window).std()
        return vol.rolling(vov_window).std()

    @staticmethod
    def intraday_intensity(
        high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series,
    ) -> pd.Series:
        hl_range = high - low
        return ((2 * close - high - low) / hl_range.replace(0, np.nan)) * volume

    @staticmethod
    def average_true_range(
        high: pd.Series, low: pd.Series, close: pd.Series, window: int,
    ) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window).mean()

    @staticmethod
    def normalized_atr(
        high: pd.Series, low: pd.Series, close: pd.Series, window: int,
    ) -> pd.Series:
        atr = VolatilityFeatures.average_true_range(high, low, close, window)
        return atr / close

    @staticmethod
    def bollinger_bandwidth(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
        mid = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = mid + n_std * std
        lower = mid - n_std * std
        return (upper - lower) / mid

    @staticmethod
    def bollinger_pct_b(close: pd.Series, window: int = 20, n_std: float = 2.0) -> pd.Series:
        mid = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = mid + n_std * std
        lower = mid - n_std * std
        return (close - lower) / (upper - lower).replace(0, np.nan)

    @staticmethod
    def ewma_volatility(returns: pd.Series, span: int) -> pd.Series:
        return returns.ewm(span=span).std() * np.sqrt(252)

    @staticmethod
    def variance_ratio(returns: pd.Series, short: int, long: int) -> pd.Series:
        """Lo-MacKinlay variance ratio — tests random walk hypothesis."""
        var_short = returns.rolling(short).var()
        var_long = returns.rolling(long).var()
        return (var_long / long) / (var_short / short).replace(0, np.nan)
