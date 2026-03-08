from __future__ import annotations

import pandas as pd
from loguru import logger

from app.analysis.indicators import swing_highs, swing_lows


def detect_liquidity_sweep(
    df: pd.DataFrame,
    lookback_swings: int = 5,
    wick_ratio_threshold: float = 0.5,
) -> list[dict]:
    """
    Detect liquidity sweeps where price wicks beyond a swing level then closes
    back inside, indicating stop-hunt / liquidity grab.

    Returns a list of sweep events with direction and key prices.
    """
    sweeps: list[dict] = []
    if len(df) < lookback_swings * 3:
        return sweeps

    sh = swing_highs(df, lookback_swings)
    sl = swing_lows(df, lookback_swings)

    swing_high_levels: list[float] = []
    swing_low_levels: list[float] = []

    for i in range(len(df) - 1):
        if sh.iloc[i]:
            swing_high_levels.append(df["high"].iloc[i])
        if sl.iloc[i]:
            swing_low_levels.append(df["low"].iloc[i])

    last_idx = len(df) - 1
    candle = df.iloc[last_idx]
    prev = df.iloc[last_idx - 1] if last_idx > 0 else candle

    body_top = max(candle["open"], candle["close"])
    body_bottom = min(candle["open"], candle["close"])
    candle_range = candle["high"] - candle["low"]

    if candle_range == 0:
        return sweeps

    upper_wick = candle["high"] - body_top
    lower_wick = body_bottom - candle["low"]

    # Bearish sweep (sweep above swing high, close back below)
    for level in swing_high_levels[-5:]:
        if (
            candle["high"] > level
            and candle["close"] < level
            and prev["close"] <= level
            and upper_wick / candle_range >= wick_ratio_threshold
        ):
            sweeps.append(
                {
                    "direction": "short",
                    "sweep_level": level,
                    "sweep_high": candle["high"],
                    "close": candle["close"],
                    "timestamp": candle.get("timestamp"),
                }
            )
            logger.debug(f"Bearish liquidity sweep at {level:.5f}")
            break

    # Bullish sweep (sweep below swing low, close back above)
    for level in swing_low_levels[-5:]:
        if (
            candle["low"] < level
            and candle["close"] > level
            and prev["close"] >= level
            and lower_wick / candle_range >= wick_ratio_threshold
        ):
            sweeps.append(
                {
                    "direction": "long",
                    "sweep_level": level,
                    "sweep_low": candle["low"],
                    "close": candle["close"],
                    "timestamp": candle.get("timestamp"),
                }
            )
            logger.debug(f"Bullish liquidity sweep at {level:.5f}")
            break

    return sweeps
