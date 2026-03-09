"""
Market regime detection and classification features.

Uses Hidden Markov Models, volatility clustering, trend analysis,
and structural break detection for regime-aware alpha generation.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


class RegimeFeatures:
    """Detect and classify market regimes for conditional strategy activation."""

    @staticmethod
    def volatility_regime(returns: pd.Series, window: int = 63, n_regimes: int = 3) -> pd.Series:
        """Classify into low/medium/high volatility regimes using rolling vol quantiles."""
        vol = returns.rolling(window).std() * np.sqrt(252)
        boundaries = np.linspace(0, 1, n_regimes + 1)[1:-1]
        expanding_quantiles = pd.DataFrame(
            {f"q_{q:.2f}": vol.expanding().quantile(q) for q in boundaries}
        )

        regime = pd.Series(0, index=returns.index, dtype=int)
        for i, q in enumerate(boundaries):
            regime = regime + (vol > expanding_quantiles.iloc[:, i]).astype(int)
        return regime

    @staticmethod
    def trend_regime(close: pd.Series, short_window: int = 21, long_window: int = 63) -> pd.Series:
        """
        Classify trend regime:
         1 = strong uptrend
         0 = range-bound / choppy
        -1 = strong downtrend
        """
        short_ma = close.rolling(short_window).mean()
        long_ma = close.rolling(long_window).mean()
        slope = close.pct_change(long_window)
        adx = RegimeFeatures._adx_proxy(close, window=14)

        regime = pd.Series(0, index=close.index, dtype=int)
        regime[(short_ma > long_ma) & (slope > 0) & (adx > 25)] = 1
        regime[(short_ma < long_ma) & (slope < 0) & (adx > 25)] = -1
        return regime

    @staticmethod
    def _adx_proxy(close: pd.Series, window: int = 14) -> pd.Series:
        """Simplified ADX proxy based on directional movement strength."""
        up = close.diff()
        down = -close.diff()
        plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0), index=close.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0), index=close.index)
        tr = close.diff().abs()
        atr = tr.rolling(window).mean()
        plus_di = 100 * plus_dm.rolling(window).mean() / atr.replace(0, np.nan)
        minus_di = 100 * minus_dm.rolling(window).mean() / atr.replace(0, np.nan)
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        return dx.rolling(window).mean()

    @staticmethod
    def hmm_regime(returns: pd.Series, n_states: int = 3, window: int = 252) -> pd.Series:
        """
        Hidden Markov Model regime detection.
        Falls back to volatility-based regime if hmmlearn is unavailable.
        """
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            logger.warning("hmmlearn not installed; falling back to volatility regime")
            return RegimeFeatures.volatility_regime(returns, window, n_states)

        regimes = pd.Series(np.nan, index=returns.index)

        for i in range(window, len(returns)):
            chunk = returns.iloc[i - window:i].dropna().values.reshape(-1, 1)
            if len(chunk) < window // 2:
                continue
            try:
                model = GaussianHMM(
                    n_components=n_states,
                    covariance_type="full",
                    n_iter=100,
                    random_state=42,
                )
                model.fit(chunk)
                state = model.predict(chunk)[-1]
                means = model.means_.flatten()
                order = np.argsort(means)
                mapping = {old: new for new, old in enumerate(order)}
                regimes.iloc[i] = mapping[state]
            except Exception:
                continue

        return regimes.ffill().fillna(0).astype(int)

    @staticmethod
    def structural_break(series: pd.Series, window: int = 126) -> pd.Series:
        """
        CUSUM-based structural break detection.
        Returns cumulative deviation from mean — large values signal breaks.
        """
        mean = series.rolling(window).mean()
        std = series.rolling(window).std().replace(0, np.nan)
        normalized = (series - mean) / std
        return normalized.cumsum()

    @staticmethod
    def market_stress_indicator(
        returns: pd.Series, vix_proxy: pd.Series, window: int = 21,
    ) -> pd.Series:
        """
        Composite stress indicator combining:
        - Return magnitude
        - Volatility level
        - Correlation with stress proxy (e.g. VIX)
        """
        ret_stress = returns.rolling(window).mean().abs() / returns.rolling(window).std().replace(0, np.nan)
        vol_stress = vix_proxy.rolling(window).mean() / vix_proxy.rolling(window * 4).mean().replace(0, np.nan)
        composite = 0.5 * ret_stress + 0.5 * vol_stress
        return composite

    @staticmethod
    def mean_reversion_score(close: pd.Series, windows: list[int] | None = None) -> pd.Series:
        """
        Composite score of how mean-reverting the current market is,
        based on variance ratios at multiple horizons.
        """
        if windows is None:
            windows = [5, 10, 21, 63]

        returns = close.pct_change()
        scores = pd.DataFrame()

        for w in windows:
            var_1 = returns.rolling(1).var()
            var_w = returns.rolling(w).var() / w
            vr = var_w / var_1.replace(0, np.nan)
            scores[f"vr_{w}"] = 1 - vr

        return scores.mean(axis=1)
