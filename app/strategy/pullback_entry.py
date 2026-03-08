from __future__ import annotations

import pandas as pd

from app.analysis.indicators import atr, ema


def find_pullback_entry(
    m5_df: pd.DataFrame,
    direction: str,
    ema_period: int = 21,
    atr_period: int = 14,
    max_distance_atr: float = 1.5,
) -> dict | None:
    """
    Look for a pullback entry on M5 toward the 21-EMA.

    For longs:  price pulled back near/below EMA-21, then current candle
                closes above with bullish body.
    For shorts: price pulled back near/above EMA-21, then current candle
                closes below with bearish body.

    Returns entry details or None.
    """
    if len(m5_df) < ema_period + 5:
        return None

    ema_vals = ema(m5_df["close"], ema_period)
    atr_vals = atr(m5_df, atr_period)

    last = m5_df.iloc[-1]
    prev = m5_df.iloc[-2]
    current_ema = ema_vals.iloc[-1]
    current_atr = atr_vals.iloc[-1]

    if current_atr == 0:
        return None

    distance = abs(last["close"] - current_ema) / current_atr

    if direction == "long":
        # Previous candle touched/crossed below EMA, current candle closes above
        pulled_back = prev["low"] <= current_ema * 1.001
        bullish_close = last["close"] > last["open"] and last["close"] > current_ema
        within_range = distance <= max_distance_atr

        if pulled_back and bullish_close and within_range:
            return {
                "entry_price": last["close"],
                "ema_value": current_ema,
                "atr_value": current_atr,
                "distance_atr": distance,
                "timestamp": last.get("timestamp"),
            }

    elif direction == "short":
        pulled_back = prev["high"] >= current_ema * 0.999
        bearish_close = last["close"] < last["open"] and last["close"] < current_ema
        within_range = distance <= max_distance_atr

        if pulled_back and bearish_close and within_range:
            return {
                "entry_price": last["close"],
                "ema_value": current_ema,
                "atr_value": current_atr,
                "distance_atr": distance,
                "timestamp": last.get("timestamp"),
            }

    return None
