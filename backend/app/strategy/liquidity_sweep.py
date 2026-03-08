"""
Liquidity Sweep Detection

A liquidity sweep occurs when price briefly breaks above a key high (sweep of buy-side
liquidity) or below a key low (sweep of sell-side liquidity), then reverses sharply.
These areas are where stop orders cluster, and institutional players hunt them before
reversing direction.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class SweepEvent:
    direction: str          # "BULLISH_SWEEP" or "BEARISH_SWEEP"
    swept_level: float
    sweep_bar_index: int
    sweep_high: float
    sweep_low: float
    rejection_strength: float   # Wick-to-body ratio (higher = stronger rejection)
    volume_spike: bool
    confirmed: bool


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def identify_swing_points(
    df: pd.DataFrame,
    lookback: int = 10,
    atr_multiplier: float = 0.5
) -> Tuple[List[float], List[float]]:
    """Return lists of significant swing highs and swing lows."""
    atr = calculate_atr(df)
    highs: List[float] = []
    lows: List[float] = []
    n = len(df)

    for i in range(lookback, n - lookback):
        window_highs = df["high"].iloc[i - lookback: i + lookback + 1]
        window_lows = df["low"].iloc[i - lookback: i + lookback + 1]

        if df["high"].iloc[i] == window_highs.max():
            highs.append(df["high"].iloc[i])
        if df["low"].iloc[i] == window_lows.min():
            lows.append(df["low"].iloc[i])

    return highs, lows


def detect_liquidity_sweep(
    df: pd.DataFrame,
    lookback_swings: int = 20,
    sweep_atr_buffer: float = 0.3,
    min_rejection_ratio: float = 0.6,
    require_close_inside: bool = True,
) -> Optional[SweepEvent]:
    """
    Detect a liquidity sweep on the most recent candles.

    Parameters
    ----------
    df : OHLCV DataFrame (sorted ascending by time, at least lookback_swings + 5 bars)
    lookback_swings : bars to look back for swing highs/lows
    sweep_atr_buffer : ATR fraction that price must exceed the level by to qualify
    min_rejection_ratio : minimum wick-to-range ratio to confirm rejection
    require_close_inside : candle must close back inside the swept range

    Returns
    -------
    SweepEvent or None
    """
    if len(df) < lookback_swings + 5:
        return None

    atr = calculate_atr(df)
    atr_now = atr.iloc[-1]
    if pd.isna(atr_now) or atr_now == 0:
        return None

    # Build reference swing levels from lookback window (exclude last 3 bars)
    ref = df.iloc[-(lookback_swings + 3): -3]
    recent = df.iloc[-3:]
    last = df.iloc[-1]

    swing_highs = []
    swing_lows = []
    for i in range(1, len(ref) - 1):
        if ref["high"].iloc[i] > ref["high"].iloc[i - 1] and ref["high"].iloc[i] > ref["high"].iloc[i + 1]:
            swing_highs.append(ref["high"].iloc[i])
        if ref["low"].iloc[i] < ref["low"].iloc[i - 1] and ref["low"].iloc[i] < ref["low"].iloc[i + 1]:
            swing_lows.append(ref["low"].iloc[i])

    if not swing_highs and not swing_lows:
        return None

    buffer = atr_now * sweep_atr_buffer

    # Check bearish sweep: price spiked above a swing high, then closed back below
    for level in sorted(swing_highs, reverse=True)[:5]:
        for idx in range(len(recent)):
            bar = recent.iloc[idx]
            swept = bar["high"] > level + buffer
            closed_inside = bar["close"] < level if require_close_inside else True

            if swept and closed_inside:
                candle_range = bar["high"] - bar["low"]
                upper_wick = bar["high"] - max(bar["open"], bar["close"])
                rejection = upper_wick / candle_range if candle_range > 0 else 0

                if rejection >= min_rejection_ratio:
                    vol_avg = df["volume"].iloc[-lookback_swings:].mean()
                    vol_spike = bool(bar["volume"] > vol_avg * 1.5)

                    return SweepEvent(
                        direction="BEARISH_SWEEP",
                        swept_level=level,
                        sweep_bar_index=len(df) - 3 + idx,
                        sweep_high=bar["high"],
                        sweep_low=bar["low"],
                        rejection_strength=rejection,
                        volume_spike=vol_spike,
                        confirmed=True,
                    )

    # Check bullish sweep: price spiked below a swing low, then closed back above
    for level in sorted(swing_lows)[:5]:
        for idx in range(len(recent)):
            bar = recent.iloc[idx]
            swept = bar["low"] < level - buffer
            closed_inside = bar["close"] > level if require_close_inside else True

            if swept and closed_inside:
                candle_range = bar["high"] - bar["low"]
                lower_wick = min(bar["open"], bar["close"]) - bar["low"]
                rejection = lower_wick / candle_range if candle_range > 0 else 0

                if rejection >= min_rejection_ratio:
                    vol_avg = df["volume"].iloc[-lookback_swings:].mean()
                    vol_spike = bool(bar["volume"] > vol_avg * 1.5)

                    return SweepEvent(
                        direction="BULLISH_SWEEP",
                        swept_level=level,
                        sweep_bar_index=len(df) - 3 + idx,
                        sweep_high=bar["high"],
                        sweep_low=bar["low"],
                        rejection_strength=rejection,
                        volume_spike=vol_spike,
                        confirmed=True,
                    )

    return None


def get_sweep_bias(sweep: SweepEvent) -> str:
    """Convert sweep type to trade bias."""
    return "SHORT" if sweep.direction == "BEARISH_SWEEP" else "LONG"
