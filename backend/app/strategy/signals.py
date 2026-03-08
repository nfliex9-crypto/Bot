from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas import Signal


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean().fillna(method="bfill")


def _swing_points(df: pd.DataFrame, lookback: int = 3) -> tuple[pd.Series, pd.Series]:
    swing_high = (
        df["high"]
        .rolling(lookback * 2 + 1, center=True)
        .apply(lambda x: 1 if x[lookback] == np.max(x) else 0, raw=True)
        .fillna(0)
        .astype(bool)
    )
    swing_low = (
        df["low"]
        .rolling(lookback * 2 + 1, center=True)
        .apply(lambda x: 1 if x[lookback] == np.min(x) else 0, raw=True)
        .fillna(0)
        .astype(bool)
    )
    return swing_high, swing_low


def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 50) -> tuple[bool, str]:
    sample = df.tail(lookback).copy()
    last = sample.iloc[-1]
    prior = sample.iloc[:-1]

    swept_high = last["high"] > prior["high"].max() and last["close"] < prior["high"].max()
    swept_low = last["low"] < prior["low"].min() and last["close"] > prior["low"].min()

    if swept_high:
        return True, "liquidity sweep above highs"
    if swept_low:
        return True, "liquidity sweep below lows"
    return False, "no liquidity sweep"


def detect_break_of_structure(df: pd.DataFrame, lookback: int = 80) -> tuple[bool, str]:
    sample = df.tail(lookback).copy()
    swing_high, swing_low = _swing_points(sample)

    highs = sample.loc[swing_high, "high"]
    lows = sample.loc[swing_low, "low"]
    if len(highs) < 2 or len(lows) < 2:
        return False, "insufficient swing data"

    close = sample["close"].iloc[-1]
    if close > highs.iloc[-2]:
        return True, "bullish BOS"
    if close < lows.iloc[-2]:
        return True, "bearish BOS"
    return False, "no BOS"


def detect_pullback_entry(df: pd.DataFrame, direction: str) -> tuple[bool, str]:
    sample = df.tail(40).copy()
    ema20 = sample["close"].ewm(span=20).mean()
    close = sample["close"].iloc[-1]
    prev = sample["close"].iloc[-2]

    if direction == "buy":
        pulled_back = close >= ema20.iloc[-1] and prev < ema20.iloc[-2]
        return pulled_back, "bullish pullback to EMA20" if pulled_back else "no buy pullback"
    if direction == "sell":
        pulled_back = close <= ema20.iloc[-1] and prev > ema20.iloc[-2]
        return pulled_back, "bearish pullback to EMA20" if pulled_back else "no sell pullback"
    return False, "direction none"


def build_signal(df: pd.DataFrame) -> Signal:
    sweep, sweep_reason = detect_liquidity_sweep(df)
    bos, bos_reason = detect_break_of_structure(df)

    direction = "none"
    if "bullish" in bos_reason or "below lows" in sweep_reason:
        direction = "buy"
    elif "bearish" in bos_reason or "above highs" in sweep_reason:
        direction = "sell"

    pullback, pullback_reason = detect_pullback_entry(df, direction)
    reason = f"{sweep_reason}; {bos_reason}; {pullback_reason}"

    if not (sweep and bos and pullback):
        direction = "none"

    return Signal(
        direction=direction,
        liquidity_sweep=sweep,
        break_of_structure=bos,
        pullback_entry=pullback,
        reason=reason,
    )
