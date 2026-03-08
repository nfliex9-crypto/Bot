"""
Feature Engineering for AI Trade Classifier.

Extracts relevant features from market data and strategy signals
to feed into the RandomForest classifier.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from app.utils.indicators import (
    calculate_atr,
    calculate_rsi,
    calculate_macd,
    calculate_ema,
    calculate_sma,
    calculate_bollinger_bands,
    find_swing_highs,
    find_swing_lows,
)
from app.core.strategy.liquidity_sweep import SweepResult
from app.core.strategy.break_of_structure import BOSResult
from app.core.strategy.pullback_entry import EntryResult
from app.core.strategy.multi_timeframe import MTFAnalysis


FEATURE_NAMES = [
    # Price structure
    "close_vs_ema9", "close_vs_ema21", "close_vs_ema50",
    "ema9_vs_ema21", "ema21_vs_ema50",

    # Momentum
    "rsi", "rsi_oversold", "rsi_overbought",
    "macd_hist", "macd_signal_cross",

    # Volatility
    "atr_pct", "bb_width", "close_vs_bb_upper", "close_vs_bb_lower",

    # Candle structure
    "body_ratio", "upper_wick_ratio", "lower_wick_ratio",
    "is_bullish_candle",

    # Sweep features
    "sweep_detected", "sweep_direction", "sweep_rejection_strength",
    "sweep_bars_ago",

    # BOS features
    "bos_detected", "bos_direction", "bos_strength",
    "bos_bars_after_sweep",

    # MTF alignment
    "h1_bias", "m15_trend", "mtf_aligned",
    "alignment_score",

    # Entry zone
    "entry_zone_fvg", "entry_zone_ob", "entry_zone_50pct",
    "risk_reward",

    # Session
    "is_london", "is_new_york", "is_overlap",

    # Additional
    "volume_ratio",  # current volume vs 20-bar avg
    "swing_high_dist", "swing_low_dist",
]


class FeatureEngineer:
    """
    Extracts features from market data and strategy analysis
    for the RandomForest classifier.
    """

    def extract(
        self,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
        mtf: MTFAnalysis,
        session: str = "unknown",
    ) -> Dict[str, float]:
        """
        Extract all features for a single prediction sample.

        Returns a dict of feature_name → float value.
        """
        features = {}

        # Price + indicator features from M5 (execution TF)
        m5_feats = self._extract_price_features(m5_df)
        features.update(m5_feats)

        # Sweep features
        sweep_feats = self._extract_sweep_features(mtf.m5_sweep)
        features.update(sweep_feats)

        # BOS features
        bos_feats = self._extract_bos_features(mtf.m5_bos)
        features.update(bos_feats)

        # MTF alignment features
        mtf_feats = self._extract_mtf_features(mtf)
        features.update(mtf_feats)

        # Entry features
        entry_feats = self._extract_entry_features(mtf.m5_entry)
        features.update(entry_feats)

        # Session features
        session_feats = self._extract_session_features(session)
        features.update(session_feats)

        return features

    def to_array(self, features: Dict[str, float]) -> np.ndarray:
        """Convert features dict to numpy array in consistent order."""
        return np.array([features.get(name, 0.0) for name in FEATURE_NAMES])

    def _extract_price_features(self, df: pd.DataFrame) -> dict:
        if len(df) < 21:
            return {k: 0.0 for k in [
                "close_vs_ema9", "close_vs_ema21", "close_vs_ema50",
                "ema9_vs_ema21", "ema21_vs_ema50",
                "rsi", "rsi_oversold", "rsi_overbought",
                "macd_hist", "macd_signal_cross",
                "atr_pct", "bb_width", "close_vs_bb_upper", "close_vs_bb_lower",
                "body_ratio", "upper_wick_ratio", "lower_wick_ratio",
                "is_bullish_candle", "volume_ratio",
                "swing_high_dist", "swing_low_dist",
            ]}

        close = df["close"].iloc[-1]
        atr = calculate_atr(df, 14).iloc[-1]

        ema9 = calculate_ema(df, 9).iloc[-1]
        ema21 = calculate_ema(df, 21).iloc[-1]
        ema50 = calculate_ema(df, 50).iloc[-1] if len(df) >= 50 else ema21

        rsi = calculate_rsi(df, 14).iloc[-1]

        macd_line, signal_line, macd_hist = calculate_macd(df)
        hist = macd_hist.iloc[-1]
        prev_hist = macd_hist.iloc[-2] if len(df) > 2 else 0.0
        macd_cross = 1.0 if (prev_hist < 0 < hist) else (-1.0 if (prev_hist > 0 > hist) else 0.0)

        bb_up, bb_mid, bb_low = calculate_bollinger_bands(df, 20, 2)
        bb_width = (bb_up.iloc[-1] - bb_low.iloc[-1]) / (close + 1e-10)

        candle = df.iloc[-1]
        candle_range = candle["high"] - candle["low"] + 1e-10
        body = abs(candle["close"] - candle["open"])
        upper_wick = candle["high"] - max(candle["open"], candle["close"])
        lower_wick = min(candle["open"], candle["close"]) - candle["low"]

        # Swing distances
        swing_h = find_swing_highs(df, 5)
        swing_l = find_swing_lows(df, 5)
        sh_dist = 0.0
        sl_dist = 0.0
        if swing_h.any():
            last_sh = df.loc[swing_h, "high"].iloc[-1]
            sh_dist = (last_sh - close) / (atr + 1e-10)
        if swing_l.any():
            last_sl = df.loc[swing_l, "low"].iloc[-1]
            sl_dist = (close - last_sl) / (atr + 1e-10)

        # Volume ratio
        vol_ratio = 1.0
        if "volume" in df.columns and df["volume"].iloc[-1] > 0:
            avg_vol = df["volume"].rolling(20).mean().iloc[-1]
            vol_ratio = df["volume"].iloc[-1] / (avg_vol + 1e-10)

        return {
            "close_vs_ema9": (close - ema9) / (atr + 1e-10),
            "close_vs_ema21": (close - ema21) / (atr + 1e-10),
            "close_vs_ema50": (close - ema50) / (atr + 1e-10),
            "ema9_vs_ema21": (ema9 - ema21) / (atr + 1e-10),
            "ema21_vs_ema50": (ema21 - ema50) / (atr + 1e-10),
            "rsi": rsi / 100.0,
            "rsi_oversold": 1.0 if rsi < 30 else 0.0,
            "rsi_overbought": 1.0 if rsi > 70 else 0.0,
            "macd_hist": np.clip(hist / (atr + 1e-10), -2, 2),
            "macd_signal_cross": macd_cross,
            "atr_pct": atr / (close + 1e-10),
            "bb_width": bb_width,
            "close_vs_bb_upper": (close - bb_up.iloc[-1]) / (atr + 1e-10),
            "close_vs_bb_lower": (close - bb_low.iloc[-1]) / (atr + 1e-10),
            "body_ratio": body / candle_range,
            "upper_wick_ratio": upper_wick / candle_range,
            "lower_wick_ratio": lower_wick / candle_range,
            "is_bullish_candle": 1.0 if candle["close"] > candle["open"] else 0.0,
            "volume_ratio": min(vol_ratio, 5.0),
            "swing_high_dist": np.clip(sh_dist, -5, 5),
            "swing_low_dist": np.clip(sl_dist, -5, 5),
        }

    def _extract_sweep_features(self, sweep: Optional[SweepResult]) -> dict:
        if sweep is None or not sweep.detected:
            return {
                "sweep_detected": 0.0,
                "sweep_direction": 0.0,
                "sweep_rejection_strength": 0.0,
                "sweep_bars_ago": 10.0,
            }
        return {
            "sweep_detected": 1.0,
            "sweep_direction": 1.0 if sweep.direction == "bullish" else -1.0,
            "sweep_rejection_strength": sweep.rejection_strength,
            "sweep_bars_ago": float(sweep.bars_ago),
        }

    def _extract_bos_features(self, bos: Optional[BOSResult]) -> dict:
        if bos is None or not bos.detected:
            return {
                "bos_detected": 0.0,
                "bos_direction": 0.0,
                "bos_strength": 0.0,
                "bos_bars_after_sweep": 15.0,
            }
        return {
            "bos_detected": 1.0,
            "bos_direction": 1.0 if bos.direction == "bullish" else -1.0,
            "bos_strength": bos.strength,
            "bos_bars_after_sweep": float(bos.bars_after_sweep),
        }

    def _extract_mtf_features(self, mtf: MTFAnalysis) -> dict:
        h1_enc = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
        m15_enc = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}
        return {
            "h1_bias": h1_enc.get(mtf.h1_bias, 0.0),
            "m15_trend": m15_enc.get(mtf.m15_trend, 0.0),
            "mtf_aligned": 1.0 if mtf.m15_aligned else 0.0,
            "alignment_score": mtf.alignment_score,
        }

    def _extract_entry_features(self, entry: Optional[EntryResult]) -> dict:
        if entry is None or not entry.valid:
            return {
                "entry_zone_fvg": 0.0,
                "entry_zone_ob": 0.0,
                "entry_zone_50pct": 0.0,
                "risk_reward": 0.0,
            }
        return {
            "entry_zone_fvg": 1.0 if entry.entry_zone_type == "fvg" else 0.0,
            "entry_zone_ob": 1.0 if entry.entry_zone_type == "ob" else 0.0,
            "entry_zone_50pct": 1.0 if entry.entry_zone_type == "50pct" else 0.0,
            "risk_reward": min(entry.risk_reward or 0.0, 5.0) / 5.0,
        }

    def _extract_session_features(self, session: str) -> dict:
        return {
            "is_london": 1.0 if "london" in session.lower() else 0.0,
            "is_new_york": 1.0 if "new_york" in session.lower() or "newyork" in session.lower() else 0.0,
            "is_overlap": 1.0 if "overlap" in session.lower() else 0.0,
        }
