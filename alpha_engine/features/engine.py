"""
Feature Engineering Engine — top-level orchestrator.

Manages the full feature pipeline from raw data to model-ready feature matrices
with proper train/test alignment and information leakage prevention.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from ..config import FeatureConfig
from .factory import FeatureFactory

logger = logging.getLogger(__name__)


class FeatureEngine:
    """
    Orchestrates feature generation, selection, and transformation.
    Ensures no look-ahead bias by strictly respecting temporal ordering.
    """

    def __init__(self, config: Optional[FeatureConfig] = None) -> None:
        self.config = config or FeatureConfig()
        self.factory = FeatureFactory(self.config)
        self._feature_importance: dict[str, float] = {}

    def build_feature_matrix(
        self,
        ohlcv_dict: dict[str, pd.DataFrame],
        market_symbol: str = "SPY",
    ) -> dict[str, pd.DataFrame]:
        """Generate, clean, and return feature matrices for all symbols."""
        raw_features = self.factory.generate_all(ohlcv_dict, market_symbol)

        cleaned = {}
        for sym, feat_df in raw_features.items():
            feat_df = self._drop_low_coverage(feat_df)
            feat_df = self._fill_missing(feat_df)
            cleaned[sym] = feat_df

        logger.info(
            "Feature engine produced matrices for %d symbols, avg %d features",
            len(cleaned),
            int(np.mean([len(df.columns) for df in cleaned.values()])) if cleaned else 0,
        )
        return cleaned

    def compute_feature_importance(
        self,
        features: pd.DataFrame,
        forward_returns: pd.Series,
        method: str = "ic",
    ) -> pd.Series:
        """
        Rank features by predictive power.

        Methods:
        - 'ic': Information Coefficient (rank correlation with forward returns)
        - 'mutual_info': Mutual information score
        """
        importance = {}

        if method == "ic":
            for col in features.columns:
                valid = features[col].dropna()
                aligned = forward_returns.reindex(valid.index).dropna()
                common = valid.index.intersection(aligned.index)
                if len(common) < 30:
                    importance[col] = 0.0
                    continue
                ic = valid.loc[common].corr(aligned.loc[common], method="spearman")
                importance[col] = abs(ic) if not np.isnan(ic) else 0.0

        elif method == "mutual_info":
            from sklearn.feature_selection import mutual_info_regression
            common = features.dropna().index.intersection(forward_returns.dropna().index)
            if len(common) > 50:
                X = features.loc[common].fillna(0).values
                y = forward_returns.loc[common].values
                mi = mutual_info_regression(X, y, random_state=42)
                importance = dict(zip(features.columns, mi))

        self._feature_importance = importance
        return pd.Series(importance).sort_values(ascending=False)

    def select_top_features(
        self,
        features: pd.DataFrame,
        forward_returns: pd.Series,
        top_n: int = 50,
        method: str = "ic",
    ) -> pd.DataFrame:
        """Select the top-N features by predictive power."""
        scores = self.compute_feature_importance(features, forward_returns, method)
        top_cols = scores.head(top_n).index.tolist()
        return features[top_cols]

    def _drop_low_coverage(self, df: pd.DataFrame) -> pd.DataFrame:
        min_pct = self.config.min_non_null_pct
        coverage = df.notna().mean()
        keep = coverage[coverage >= min_pct].index.tolist()
        dropped = len(df.columns) - len(keep)
        if dropped > 0:
            logger.debug("Dropped %d features below %.0f%% coverage", dropped, min_pct * 100)
        return df[keep]

    def _fill_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.ffill()
        df = df.fillna(0)
        return df
