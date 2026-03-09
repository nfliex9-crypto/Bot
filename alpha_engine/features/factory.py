"""
Feature Factory — bulk generation of hundreds of candidate alpha factors.

Orchestrates all feature generators and produces a unified feature matrix
suitable for strategy generation and ML model training.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from ..config import FeatureConfig
from .statistical import StatisticalFeatures
from .volatility import VolatilityFeatures
from .cross_market import CrossMarketFeatures
from .regime import RegimeFeatures

logger = logging.getLogger(__name__)


class FeatureFactory:
    """
    Generates a comprehensive feature matrix from raw OHLCV data.

    Each feature is named with a structured convention:
    {category}_{metric}_{window}
    """

    def __init__(self, config: Optional[FeatureConfig] = None) -> None:
        self.config = config or FeatureConfig()
        self.stat = StatisticalFeatures()
        self.vol = VolatilityFeatures()
        self.cross = CrossMarketFeatures()
        self.regime = RegimeFeatures()

    def generate_single_asset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate all single-asset features from OHLCV data."""
        features = pd.DataFrame(index=df.index)
        o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
        returns = c.pct_change()
        log_ret = self.stat.log_returns(c)

        for w in self.config.momentum_windows:
            features[f"mom_{w}"] = self.stat.momentum(c, w)
            features[f"roc_{w}"] = self.stat.rate_of_change(c, w)

        for w in self.config.zscore_windows:
            features[f"zscore_close_{w}"] = self.stat.rolling_zscore(c, w)
            features[f"zscore_volume_{w}"] = self.stat.rolling_zscore(v, w)
            features[f"zscore_ret_{w}"] = self.stat.rolling_zscore(returns, w)

        for w in self.config.lookback_windows:
            features[f"rank_close_{w}"] = self.stat.rolling_rank(c, w)
            features[f"rank_volume_{w}"] = self.stat.rolling_rank(v, w)

        for w in self.config.lookback_windows:
            features[f"skew_{w}"] = self.stat.rolling_skew(returns, w)
            features[f"kurt_{w}"] = self.stat.rolling_kurtosis(returns, w)

        for lag in [1, 2, 3, 5]:
            features[f"autocorr_{lag}_63"] = self.stat.autocorrelation(returns, lag, 63)

        features["entropy_63"] = self.stat.rolling_entropy(returns, 63)
        features["entropy_126"] = self.stat.rolling_entropy(returns, 126)

        for w in self.config.volatility_windows:
            features[f"rvol_{w}"] = self.vol.realized_volatility(returns, w)
            features[f"parkinson_{w}"] = self.vol.parkinson_volatility(h, l, w)
            features[f"gk_{w}"] = self.vol.garman_klass_volatility(o, h, l, c, w)
            features[f"atr_{w}"] = self.vol.average_true_range(h, l, c, w)
            features[f"natr_{w}"] = self.vol.normalized_atr(h, l, c, w)

        features["yz_vol_21"] = self.vol.yang_zhang_volatility(o, h, l, c, 21)
        features["yz_vol_63"] = self.vol.yang_zhang_volatility(o, h, l, c, 63)

        features["vol_ratio_5_21"] = self.vol.volatility_ratio(returns, 5, 21)
        features["vol_ratio_21_63"] = self.vol.volatility_ratio(returns, 21, 63)
        features["vol_of_vol"] = self.vol.volatility_of_volatility(returns, 21, 63)

        features["bb_width_20"] = self.vol.bollinger_bandwidth(c, 20)
        features["bb_pctb_20"] = self.vol.bollinger_pct_b(c, 20)
        features["ewma_vol_10"] = self.vol.ewma_volatility(returns, 10)
        features["ewma_vol_21"] = self.vol.ewma_volatility(returns, 21)

        features["vr_5_20"] = self.vol.variance_ratio(returns, 5, 20)
        features["vr_10_40"] = self.vol.variance_ratio(returns, 10, 40)

        features["intraday_intensity"] = self.vol.intraday_intensity(h, l, c, v)

        features["vol_regime"] = self.regime.volatility_regime(returns)
        features["trend_regime"] = self.regime.trend_regime(c)
        features["mr_score"] = self.regime.mean_reversion_score(c)
        features["cusum"] = self.regime.structural_break(returns)

        for w in [5, 10, 21]:
            features[f"high_low_range_{w}"] = ((h - l) / c).rolling(w).mean()
            features[f"close_location_{w}"] = ((c - l) / (h - l).replace(0, np.nan)).rolling(w).mean()

        features["gap"] = o / c.shift(1) - 1
        features["body_ratio"] = (c - o).abs() / (h - l).replace(0, np.nan)
        features["upper_shadow"] = (h - pd.concat([o, c], axis=1).max(axis=1)) / (h - l).replace(0, np.nan)
        features["lower_shadow"] = (pd.concat([o, c], axis=1).min(axis=1) - l) / (h - l).replace(0, np.nan)

        for w in [5, 10, 21]:
            features[f"volume_ma_ratio_{w}"] = v / v.rolling(w).mean().replace(0, np.nan)
            features[f"dollar_volume_{w}"] = (c * v).rolling(w).mean()
            up_vol = (v * (returns > 0).astype(float)).rolling(w).sum()
            dn_vol = (v * (returns <= 0).astype(float)).rolling(w).sum()
            features[f"volume_imbalance_{w}"] = (up_vol - dn_vol) / (up_vol + dn_vol).replace(0, np.nan)

        lagged = self.stat.lagged_features(returns, self.config.max_lag)
        for col in lagged.columns:
            features[f"ret_{col}"] = lagged[col]

        if self.config.rank_normalize:
            numeric_cols = features.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                if features[col].nunique() > 10:
                    features[col] = features[col].rank(pct=True)

        if self.config.winsorize_pct > 0:
            numeric_cols = features.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                lo = features[col].quantile(self.config.winsorize_pct)
                hi = features[col].quantile(1 - self.config.winsorize_pct)
                features[col] = features[col].clip(lo, hi)

        logger.info("Generated %d single-asset features", len(features.columns))
        return features

    def generate_cross_asset(
        self,
        returns_matrix: pd.DataFrame,
        market_col: str = "SPY",
    ) -> pd.DataFrame:
        """Generate cross-asset features from a returns matrix."""
        features = pd.DataFrame(index=returns_matrix.index)

        if market_col in returns_matrix.columns:
            mkt = returns_matrix[market_col]
            for col in returns_matrix.columns:
                if col == market_col:
                    continue
                features[f"beta_{col}_63"] = self.stat.rolling_beta(returns_matrix[col], mkt, 63)
                features[f"ir_{col}_63"] = self.stat.information_ratio(returns_matrix[col], mkt, 63)

        features["dispersion_21"] = self.cross.dispersion(returns_matrix, 21)
        features["dispersion_63"] = self.cross.dispersion(returns_matrix, 63)

        sector_mom = self.cross.sector_momentum(returns_matrix, 21)
        for col in sector_mom.columns:
            features[f"xsmom_{col}"] = sector_mom[col]

        try:
            pca = self.cross.pca_factor_loadings(returns_matrix, 63, 3)
            for col in pca.columns:
                features[col] = pca[col]
        except Exception as e:
            logger.warning("PCA feature generation failed: %s", e)

        logger.info("Generated %d cross-asset features", len(features.columns))
        return features

    def generate_all(
        self,
        ohlcv_dict: dict[str, pd.DataFrame],
        market_symbol: str = "SPY",
    ) -> dict[str, pd.DataFrame]:
        """Generate complete feature sets for all assets."""
        all_features: dict[str, pd.DataFrame] = {}

        for sym, df in ohlcv_dict.items():
            try:
                all_features[sym] = self.generate_single_asset(df)
            except Exception as e:
                logger.error("Feature generation failed for %s: %s", sym, e)

        returns_matrix = pd.DataFrame(
            {sym: df["close"].pct_change() for sym, df in ohlcv_dict.items()}
        ).dropna(how="all")

        if len(returns_matrix.columns) > 1:
            cross_feats = self.generate_cross_asset(returns_matrix, market_symbol)
            for sym in all_features:
                all_features[sym] = pd.concat(
                    [all_features[sym], cross_feats.reindex(all_features[sym].index)],
                    axis=1,
                )

        return all_features
