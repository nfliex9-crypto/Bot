"""
Feature engineering for the RandomForest classifier.

Extracts a fixed-length feature vector from MTFSignal analysis results.
Features include price action, momentum, structure, and session context.
"""

from typing import Dict, Optional, List
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.strategy.multi_timeframe import MTFSignal, TimeframeAnalysis
from src.strategy.indicators import calculate_atr, calculate_rsi, calculate_ema


FEATURE_NAMES = [
    # ─── Price Action ─────────────────────────────────────────────────────────
    "htf_ema_diff_pct",         # (ema_fast - ema_slow) / ema_slow on H1
    "mtf_ema_diff_pct",         # Same on M15
    "ltf_ema_diff_pct",         # Same on M5
    "htf_rsi",                  # RSI H1
    "mtf_rsi",                  # RSI M15
    "ltf_rsi",                  # RSI M5

    # ─── Structure ────────────────────────────────────────────────────────────
    "htf_bos_detected",         # Binary: H1 BOS detected
    "mtf_bos_detected",         # Binary: M15 BOS detected
    "ltf_bos_detected",         # Binary: M5 BOS detected
    "mtf_bos_strength",         # BOS strength score M15
    "ltf_bos_strength",         # BOS strength score M5
    "htf_is_bullish",           # 1 = bullish bias on H1

    # ─── Liquidity ────────────────────────────────────────────────────────────
    "ltf_sweep_detected",       # Binary: sweep on M5
    "ltf_sweep_strength",       # Sweep strength score
    "mtf_sweep_detected",       # Binary: sweep on M15
    "ltf_sweep_aligned",        # 1 if sweep direction matches trade direction

    # ─── Pullback ─────────────────────────────────────────────────────────────
    "ltf_pullback_valid",       # Binary: valid pullback entry
    "ltf_pullback_fib",         # Fibonacci retracement level (0–1)
    "pullback_ob",              # 1 if entry type is order_block
    "pullback_fvg",             # 1 if entry type is fvg

    # ─── ATR Context ─────────────────────────────────────────────────────────
    "atr_pct_of_price",         # ATR / entry_price (volatility normalised)
    "risk_reward_ratio",        # R:R ratio for the trade

    # ─── Candle Pattern ──────────────────────────────────────────────────────
    "ltf_last_body_pct",        # Last candle body as % of range
    "ltf_upper_wick_pct",       # Upper wick as % of range
    "ltf_lower_wick_pct",       # Lower wick as % of range
    "ltf_bullish_candle",       # Last candle bullish

    # ─── Session ─────────────────────────────────────────────────────────────
    "is_london",                # In London session
    "is_newyork",               # In New York session
    "is_overlap",               # London/NY overlap
    "hour_sin",                 # Hour encoded as sin
    "hour_cos",                 # Hour encoded as cos
]

N_FEATURES = len(FEATURE_NAMES)


def extract_features(signal: MTFSignal, now: Optional[datetime] = None) -> np.ndarray:
    """
    Extract a fixed-length feature vector from an MTFSignal.
    Returns ndarray of shape (N_FEATURES,).
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    direction_val = 1 if signal.direction == "bullish" else 0
    feat = {}

    # ─── EMA diffs ────────────────────────────────────────────────────────────
    def _ema_diff(tf: TimeframeAnalysis) -> float:
        if tf.ema_slow == 0:
            return 0.0
        return (tf.ema_fast - tf.ema_slow) / tf.ema_slow

    feat["htf_ema_diff_pct"] = _ema_diff(signal.htf)
    feat["mtf_ema_diff_pct"] = _ema_diff(signal.mtf)
    feat["ltf_ema_diff_pct"] = _ema_diff(signal.ltf)

    # ─── RSI ──────────────────────────────────────────────────────────────────
    feat["htf_rsi"] = signal.htf.rsi / 100.0
    feat["mtf_rsi"] = signal.mtf.rsi / 100.0
    feat["ltf_rsi"] = signal.ltf.rsi / 100.0

    # ─── Structure ────────────────────────────────────────────────────────────
    feat["htf_bos_detected"] = float(signal.htf.bos.detected)
    feat["mtf_bos_detected"] = float(signal.mtf.bos.detected)
    feat["ltf_bos_detected"] = float(signal.ltf.bos.detected)
    feat["mtf_bos_strength"] = signal.mtf.bos.strength
    feat["ltf_bos_strength"] = signal.ltf.bos.strength
    feat["htf_is_bullish"] = float(signal.htf.trend == "bullish")

    # ─── Liquidity ────────────────────────────────────────────────────────────
    feat["ltf_sweep_detected"] = float(signal.ltf.sweep.detected)
    feat["ltf_sweep_strength"] = signal.ltf.sweep.strength
    feat["mtf_sweep_detected"] = float(signal.mtf.sweep.detected)
    if signal.ltf.sweep.detected and signal.direction:
        feat["ltf_sweep_aligned"] = float(signal.ltf.sweep.direction == signal.direction)
    else:
        feat["ltf_sweep_aligned"] = 0.0

    # ─── Pullback ─────────────────────────────────────────────────────────────
    feat["ltf_pullback_valid"] = float(signal.ltf.pullback.valid)
    feat["ltf_pullback_fib"] = signal.ltf.pullback.fib_retracement or 0.0
    feat["pullback_ob"] = float(signal.ltf.pullback.entry_type == "order_block")
    feat["pullback_fvg"] = float(signal.ltf.pullback.entry_type == "fvg")

    # ─── ATR Context ─────────────────────────────────────────────────────────
    entry = signal.entry_price or signal.ltf.current_price
    atr = signal.atr or signal.ltf.atr
    feat["atr_pct_of_price"] = (atr / entry) if entry > 0 else 0.0
    feat["risk_reward_ratio"] = min(signal.risk_reward or 0.0, 5.0) / 5.0

    # ─── Candle Pattern ──────────────────────────────────────────────────────
    if not signal.ltf.raw_df.empty:
        last = signal.ltf.raw_df.iloc[-1]
        bar_range = last["high"] - last["low"]
        if bar_range > 0:
            body = abs(last["close"] - last["open"])
            upper_wick = last["high"] - max(last["open"], last["close"])
            lower_wick = min(last["open"], last["close"]) - last["low"]
            feat["ltf_last_body_pct"] = body / bar_range
            feat["ltf_upper_wick_pct"] = upper_wick / bar_range
            feat["ltf_lower_wick_pct"] = lower_wick / bar_range
        else:
            feat["ltf_last_body_pct"] = 0.5
            feat["ltf_upper_wick_pct"] = 0.25
            feat["ltf_lower_wick_pct"] = 0.25
        feat["ltf_bullish_candle"] = float(last["close"] > last["open"])
    else:
        feat["ltf_last_body_pct"] = 0.5
        feat["ltf_upper_wick_pct"] = 0.25
        feat["ltf_lower_wick_pct"] = 0.25
        feat["ltf_bullish_candle"] = float(direction_val)

    # ─── Session ─────────────────────────────────────────────────────────────
    hour = now.hour
    feat["is_london"] = float(7 <= hour < 16)
    feat["is_newyork"] = float(12 <= hour < 21)
    feat["is_overlap"] = float(12 <= hour < 16)
    feat["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    feat["hour_cos"] = np.cos(2 * np.pi * hour / 24)

    # Build ordered array
    vector = np.array([feat[name] for name in FEATURE_NAMES], dtype=np.float64)
    # Replace NaN/inf with 0
    vector = np.nan_to_num(vector, nan=0.0, posinf=1.0, neginf=-1.0)
    return vector


def extract_batch_features(signals: list, nows: Optional[list] = None) -> np.ndarray:
    """Extract features for multiple signals. Returns (N, N_FEATURES) array."""
    if nows is None:
        nows = [None] * len(signals)
    return np.vstack([extract_features(s, t) for s, t in zip(signals, nows)])
