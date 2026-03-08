"""
Break of Structure (BOS) Detection

A Break of Structure is a significant price move that breaks a key swing high/low,
confirming a shift in market direction. This is combined with the liquidity sweep
to confirm the trade direction before looking for pullback entry.

BOS after a bullish sweep -> LONG bias confirmed
BOS after a bearish sweep -> SHORT bias confirmed
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional


@dataclass
class BOSEvent:
    direction: str              # "BULLISH_BOS" or "BEARISH_BOS"
    broken_level: float
    break_bar_index: int
    break_candle_close: float
    impulse_size: float         # Size of the breaking candle relative to ATR
    structure_strength: float   # How many bars the structure held
    confirmed: bool


def detect_break_of_structure(
    df: pd.DataFrame,
    bias: str,
    lookback: int = 15,
    min_impulse_atr: float = 0.8,
    require_candle_close: bool = True,
) -> Optional[BOSEvent]:
    """
    Detect a Break of Structure consistent with the given bias.

    Parameters
    ----------
    df : OHLCV DataFrame sorted ascending
    bias : "LONG" (look for bullish BOS) or "SHORT" (look for bearish BOS)
    lookback : bars to look back for structure levels
    min_impulse_atr : minimum candle body size in ATR units to qualify as BOS
    require_candle_close : candle must close beyond the level (not just wick)

    Returns
    -------
    BOSEvent or None
    """
    if len(df) < lookback + 5:
        return None

    from app.strategy.liquidity_sweep import calculate_atr

    atr = calculate_atr(df)
    atr_now = atr.iloc[-1]
    if pd.isna(atr_now) or atr_now == 0:
        return None

    # Reference window: exclude the most recent 1 bar (current developing candle)
    ref = df.iloc[-(lookback + 1): -1]
    analysis_bars = df.iloc[-5:]  # Last 5 bars to check for BOS

    if bias == "LONG":
        # Look for price breaking above the last significant swing high
        # Identifies the most recent swing high in the reference window
        swing_high = None
        for i in range(1, len(ref) - 1):
            if ref["high"].iloc[i] > ref["high"].iloc[i - 1] and ref["high"].iloc[i] > ref["high"].iloc[i + 1]:
                swing_high = ref["high"].iloc[i]

        if swing_high is None:
            swing_high = ref["high"].max()

        # Check if recent bars broke above it with conviction
        for idx in range(len(analysis_bars)):
            bar = analysis_bars.iloc[idx]
            close_above = bar["close"] > swing_high if require_candle_close else bar["high"] > swing_high
            body_size = abs(bar["close"] - bar["open"])
            impulse_ok = body_size >= atr_now * min_impulse_atr
            bullish_candle = bar["close"] > bar["open"]

            if close_above and impulse_ok and bullish_candle:
                bars_held = _count_structure_bars(ref, swing_high, "high")
                return BOSEvent(
                    direction="BULLISH_BOS",
                    broken_level=swing_high,
                    break_bar_index=len(df) - 5 + idx,
                    break_candle_close=bar["close"],
                    impulse_size=body_size / atr_now,
                    structure_strength=float(bars_held),
                    confirmed=True,
                )

    elif bias == "SHORT":
        # Look for price breaking below the last significant swing low
        swing_low = None
        for i in range(1, len(ref) - 1):
            if ref["low"].iloc[i] < ref["low"].iloc[i - 1] and ref["low"].iloc[i] < ref["low"].iloc[i + 1]:
                swing_low = ref["low"].iloc[i]

        if swing_low is None:
            swing_low = ref["low"].min()

        for idx in range(len(analysis_bars)):
            bar = analysis_bars.iloc[idx]
            close_below = bar["close"] < swing_low if require_candle_close else bar["low"] < swing_low
            body_size = abs(bar["close"] - bar["open"])
            impulse_ok = body_size >= atr_now * min_impulse_atr
            bearish_candle = bar["close"] < bar["open"]

            if close_below and impulse_ok and bearish_candle:
                bars_held = _count_structure_bars(ref, swing_low, "low")
                return BOSEvent(
                    direction="BEARISH_BOS",
                    broken_level=swing_low,
                    break_bar_index=len(df) - 5 + idx,
                    break_candle_close=bar["close"],
                    impulse_size=body_size / atr_now,
                    structure_strength=float(bars_held),
                    confirmed=True,
                )

    return None


def _count_structure_bars(df: pd.DataFrame, level: float, column: str) -> int:
    """Count how many consecutive bars the structure level held without being broken."""
    count = 0
    for i in range(len(df) - 1, -1, -1):
        val = df[column].iloc[i]
        if column == "high" and val < level:
            count += 1
        elif column == "low" and val > level:
            count += 1
        else:
            break
    return count


def get_bos_entry_zone(bos: BOSEvent, atr: float) -> tuple:
    """
    After BOS, define pullback entry zone (50-61.8% retracement into the BOS candle).
    Returns (zone_low, zone_high).
    """
    if bos.direction == "BULLISH_BOS":
        # Price broke above; expect pullback toward broken level
        zone_high = bos.broken_level + atr * 0.3
        zone_low = bos.broken_level - atr * 0.2
    else:
        # Price broke below; expect pullback toward broken level
        zone_low = bos.broken_level - atr * 0.3
        zone_high = bos.broken_level + atr * 0.2

    return zone_low, zone_high
