"""
Feature Engineering

Extracts ML features from OHLCV data and strategy signals for the
Random Forest classifier.
"""

import pandas as pd
import numpy as np

from app.strategy.indicators import (
    calculate_atr, calculate_rsi, calculate_ema,
    calculate_macd, calculate_bollinger_bands, calculate_stochastic,
    find_swing_highs, find_swing_lows,
)


class FeatureEngineer:
    """Generates feature vectors for the AI classifier."""

    FEATURE_COLUMNS = [
        "atr_norm", "rsi", "rsi_slope", "macd_hist", "macd_hist_slope",
        "bb_position", "bb_width", "stoch_k", "stoch_d", "stoch_cross",
        "ema_20_dist", "ema_50_dist", "ema_cross",
        "candle_body_ratio", "upper_wick_ratio", "lower_wick_ratio",
        "volume_sma_ratio", "volume_slope",
        "swing_high_dist", "swing_low_dist",
        "returns_1", "returns_5", "returns_10",
        "volatility_5", "volatility_20",
        "higher_highs", "lower_lows",
        "trend_strength",
    ]

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract all features from OHLCV data."""
        if len(df) < 60:
            return pd.DataFrame()

        features = pd.DataFrame(index=df.index)

        atr = calculate_atr(df)
        features["atr_norm"] = atr / df["close"]

        rsi = calculate_rsi(df["close"])
        features["rsi"] = rsi / 100.0
        features["rsi_slope"] = rsi.diff(3) / 100.0

        macd_line, signal_line, histogram = calculate_macd(df["close"])
        features["macd_hist"] = histogram / df["close"]
        features["macd_hist_slope"] = histogram.diff(3) / df["close"]

        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(df["close"])
        bb_range = bb_upper - bb_lower
        features["bb_position"] = (df["close"] - bb_lower) / bb_range.replace(0, np.nan)
        features["bb_width"] = bb_range / bb_middle

        stoch_k, stoch_d = calculate_stochastic(df)
        features["stoch_k"] = stoch_k / 100.0
        features["stoch_d"] = stoch_d / 100.0
        features["stoch_cross"] = (stoch_k - stoch_d) / 100.0

        ema_20 = calculate_ema(df["close"], 20)
        ema_50 = calculate_ema(df["close"], 50)
        features["ema_20_dist"] = (df["close"] - ema_20) / df["close"]
        features["ema_50_dist"] = (df["close"] - ema_50) / df["close"]
        features["ema_cross"] = (ema_20 - ema_50) / df["close"]

        body = (df["close"] - df["open"]).abs()
        total_range = (df["high"] - df["low"]).replace(0, np.nan)
        features["candle_body_ratio"] = body / total_range
        features["upper_wick_ratio"] = (df["high"] - df[["close", "open"]].max(axis=1)) / total_range
        features["lower_wick_ratio"] = (df[["close", "open"]].min(axis=1) - df["low"]) / total_range

        vol_sma = df["volume"].rolling(20).mean()
        features["volume_sma_ratio"] = df["volume"] / vol_sma.replace(0, np.nan)
        features["volume_slope"] = df["volume"].pct_change(5)

        swing_highs = find_swing_highs(df, 5)
        swing_lows = find_swing_lows(df, 5)
        last_sh = df["high"].where(swing_highs).ffill()
        last_sl = df["low"].where(swing_lows).ffill()
        features["swing_high_dist"] = (df["close"] - last_sh) / df["close"]
        features["swing_low_dist"] = (df["close"] - last_sl) / df["close"]

        features["returns_1"] = df["close"].pct_change(1)
        features["returns_5"] = df["close"].pct_change(5)
        features["returns_10"] = df["close"].pct_change(10)

        features["volatility_5"] = df["close"].pct_change().rolling(5).std()
        features["volatility_20"] = df["close"].pct_change().rolling(20).std()

        hh = (df["high"] > df["high"].shift(1)) & (df["high"].shift(1) > df["high"].shift(2))
        ll = (df["low"] < df["low"].shift(1)) & (df["low"].shift(1) < df["low"].shift(2))
        features["higher_highs"] = hh.astype(float)
        features["lower_lows"] = ll.astype(float)

        adx_period = 14
        plus_dm = df["high"].diff()
        minus_dm = -df["low"].diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
        atr_14 = calculate_atr(df, adx_period)
        plus_di = 100 * (plus_dm.rolling(adx_period).mean() / atr_14.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(adx_period).mean() / atr_14.replace(0, np.nan))
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        features["trend_strength"] = dx.rolling(adx_period).mean() / 100.0

        features = features.replace([np.inf, -np.inf], np.nan)
        features = features.fillna(0)

        return features

    def extract_trade_features(
        self,
        df: pd.DataFrame,
        entry_idx: int,
        direction: str,
        strategy_name: str,
    ) -> dict:
        """Extract features for a specific trade setup."""
        features = self.extract_features(df)
        if features.empty or entry_idx >= len(features):
            return {}

        row = features.iloc[entry_idx]
        feature_dict = row.to_dict()

        feature_dict["direction_long"] = 1.0 if direction == "long" else 0.0
        feature_dict["strategy_bos"] = 1.0 if "BOS" in strategy_name else 0.0
        feature_dict["strategy_sweep"] = 1.0 if "Sweep" in strategy_name else 0.0
        feature_dict["strategy_pullback"] = 1.0 if "Pullback" in strategy_name else 0.0

        return feature_dict

    def create_labels(
        self,
        df: pd.DataFrame,
        forward_bars: int = 20,
        profit_threshold: float = 0.005,
    ) -> pd.Series:
        """Create binary labels: 1 = profitable trade, 0 = losing trade."""
        future_return = df["close"].shift(-forward_bars) / df["close"] - 1
        labels = (future_return.abs() > profit_threshold).astype(int)
        labels[future_return < -profit_threshold] = 0
        labels[future_return > profit_threshold] = 1
        return labels
