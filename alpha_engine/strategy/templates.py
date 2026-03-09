"""
Strategy Templates — parameterized building blocks for alpha generation.

Each template produces a position signal series (values in [-1, 1]) from
features and parameters. Templates are composed by the StrategyGenerator
to create thousands of candidate strategies.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class StrategyTemplates:
    """Library of parameterized strategy signal generators."""

    @staticmethod
    def momentum_crossover(
        close: pd.Series,
        fast_window: int = 10,
        slow_window: int = 50,
        smoothing: int = 3,
    ) -> pd.Series:
        fast = close.rolling(fast_window).mean()
        slow = close.rolling(slow_window).mean()
        raw_signal = (fast - slow) / slow.replace(0, np.nan)
        return raw_signal.rolling(smoothing).mean().clip(-1, 1)

    @staticmethod
    def mean_reversion_zscore(
        close: pd.Series,
        lookback: int = 21,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
    ) -> pd.Series:
        """Enter on extreme z-scores, exit near mean."""
        mean = close.rolling(lookback).mean()
        std = close.rolling(lookback).std().replace(0, np.nan)
        z = (close - mean) / std

        signal = pd.Series(0.0, index=close.index)
        signal[z < -entry_z] = 1.0
        signal[z > entry_z] = -1.0
        signal[(z > -exit_z) & (z < exit_z)] = 0.0
        return signal.ffill()

    @staticmethod
    def breakout(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        lookback: int = 20,
        atr_mult: float = 1.5,
    ) -> pd.Series:
        """Donchian channel breakout with ATR filter."""
        upper = high.rolling(lookback).max()
        lower = low.rolling(lookback).min()

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(lookback).mean()
        threshold = atr * atr_mult

        signal = pd.Series(0.0, index=close.index)
        signal[(close > upper.shift(1)) & ((close - upper.shift(1)) > threshold * 0.3)] = 1.0
        signal[(close < lower.shift(1)) & ((lower.shift(1) - close) > threshold * 0.3)] = -1.0
        return signal

    @staticmethod
    def volatility_regime_switch(
        returns: pd.Series,
        vol_window: int = 21,
        regime_threshold: float = 0.5,
    ) -> pd.Series:
        """
        Momentum in low-vol regimes, mean-reversion in high-vol regimes.
        """
        vol = returns.rolling(vol_window).std()
        vol_pctile = vol.rolling(252).rank(pct=True)

        mom_signal = returns.rolling(vol_window).mean()
        mr_signal = -returns.rolling(vol_window // 2).mean()

        signal = pd.Series(0.0, index=returns.index)
        low_vol = vol_pctile < regime_threshold
        signal[low_vol] = mom_signal[low_vol]
        signal[~low_vol] = mr_signal[~low_vol]

        max_abs = signal.abs().rolling(63).quantile(0.95).replace(0, np.nan)
        return (signal / max_abs).clip(-1, 1)

    @staticmethod
    def statistical_arbitrage(
        asset_a: pd.Series,
        asset_b: pd.Series,
        lookback: int = 63,
        entry_z: float = 2.0,
    ) -> pd.Series:
        """Pairs trading on log-spread z-score."""
        spread = np.log(asset_a) - np.log(asset_b)
        mean = spread.rolling(lookback).mean()
        std = spread.rolling(lookback).std().replace(0, np.nan)
        z = (spread - mean) / std

        signal = pd.Series(0.0, index=asset_a.index)
        signal[z > entry_z] = -1.0
        signal[z < -entry_z] = 1.0
        signal[z.abs() < 0.5] = 0.0
        return signal.ffill()

    @staticmethod
    def cross_asset_momentum(
        returns_matrix: pd.DataFrame,
        lookback: int = 21,
        top_n: int = 3,
        bottom_n: int = 3,
    ) -> pd.DataFrame:
        """Cross-sectional momentum — long winners, short losers."""
        cum_ret = returns_matrix.rolling(lookback).sum()
        ranks = cum_ret.rank(axis=1, pct=True)

        n_assets = len(returns_matrix.columns)
        long_thresh = 1 - top_n / n_assets
        short_thresh = bottom_n / n_assets

        signals = pd.DataFrame(0.0, index=returns_matrix.index, columns=returns_matrix.columns)
        signals[ranks >= long_thresh] = 1.0
        signals[ranks <= short_thresh] = -1.0

        row_sums = signals.abs().sum(axis=1).replace(0, np.nan)
        return signals.div(row_sums, axis=0)

    @staticmethod
    def factor_combination(
        features: pd.DataFrame,
        weights: dict[str, float],
    ) -> pd.Series:
        """Weighted linear combination of ranked features."""
        combined = pd.Series(0.0, index=features.index)
        total_weight = sum(abs(w) for w in weights.values())
        if total_weight == 0:
            return combined

        for feat_name, weight in weights.items():
            if feat_name in features.columns:
                ranked = features[feat_name].rank(pct=True) - 0.5
                combined += weight * ranked / total_weight

        return combined.clip(-1, 1)

    @staticmethod
    def ml_signal(
        features: pd.DataFrame,
        forward_returns: pd.Series,
        train_window: int = 252,
        retrain_freq: int = 21,
    ) -> pd.Series:
        """Rolling ML-based signal using gradient boosting."""
        from sklearn.ensemble import GradientBoostingRegressor

        signal = pd.Series(0.0, index=features.index)
        common = features.index.intersection(forward_returns.index)
        features_aligned = features.loc[common].fillna(0)
        target_aligned = forward_returns.loc[common]

        for i in range(train_window, len(common), retrain_freq):
            train_end = i
            train_start = max(0, i - train_window)

            X_train = features_aligned.iloc[train_start:train_end].values
            y_train = target_aligned.iloc[train_start:train_end].values

            pred_end = min(i + retrain_freq, len(common))
            X_pred = features_aligned.iloc[i:pred_end].values

            if len(X_train) < 50 or len(X_pred) == 0:
                continue

            model = GradientBoostingRegressor(
                n_estimators=100, max_depth=3, learning_rate=0.1,
                subsample=0.8, random_state=42,
            )
            model.fit(X_train, y_train)
            preds = model.predict(X_pred)

            idx = common[i:pred_end]
            signal.loc[idx] = preds

        max_abs = signal.abs().quantile(0.95)
        if max_abs > 0:
            signal = signal / max_abs
        return signal.clip(-1, 1)

    @staticmethod
    def regime_switching(
        close: pd.Series,
        returns: pd.Series,
        regime: pd.Series,
        strategies: dict[int, str],
        params: dict[str, dict],
    ) -> pd.Series:
        """
        Switch between strategies based on detected regime.

        strategies maps regime_id -> strategy_name
        params maps strategy_name -> parameters
        """
        signal = pd.Series(0.0, index=close.index)
        templates = StrategyTemplates()

        for regime_id, strat_name in strategies.items():
            mask = regime == regime_id
            if not mask.any():
                continue

            p = params.get(strat_name, {})
            if strat_name == "momentum":
                s = templates.momentum_crossover(close, **p)
            elif strat_name == "mean_reversion":
                s = templates.mean_reversion_zscore(close, **p)
            elif strat_name == "breakout":
                s = templates.breakout(close, close, close, **p)
            else:
                continue

            signal[mask] = s[mask]

        return signal
