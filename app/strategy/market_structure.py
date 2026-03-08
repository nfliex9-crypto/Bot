from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


Direction = Literal["bullish", "bearish"]


@dataclass(slots=True)
class StrategySignal:
    side: Literal["buy", "sell"]
    entry: float
    stop_loss: float
    structure_stop: float
    atr_stop: float
    reasons: list[str]


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    data = df.copy()
    data["prev_close"] = data["close"].shift(1)
    tr = np.maximum(
        data["high"] - data["low"],
        np.maximum(
            (data["high"] - data["prev_close"]).abs(),
            (data["low"] - data["prev_close"]).abs(),
        ),
    )
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr) if pd.notna(atr) else float((data["high"] - data["low"]).tail(period).mean())


def _swing_levels(df: pd.DataFrame, lookback: int = 20) -> tuple[float, float]:
    recent = df.tail(lookback)
    return float(recent["high"].max()), float(recent["low"].min())


def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 20) -> Direction | None:
    if len(df) < lookback + 2:
        return None
    prev = df.iloc[:-1]
    last = df.iloc[-1]
    swing_high, swing_low = _swing_levels(prev, lookback=lookback)

    swept_high = last["high"] > swing_high and last["close"] < swing_high
    swept_low = last["low"] < swing_low and last["close"] > swing_low

    if swept_low:
        return "bullish"
    if swept_high:
        return "bearish"
    return None


def detect_break_of_structure(df: pd.DataFrame, direction: Direction, lookback: int = 10) -> bool:
    if len(df) < lookback + 2:
        return False
    prev = df.iloc[:-1]
    last_close = float(df.iloc[-1]["close"])
    prior_high = float(prev["high"].tail(lookback).max())
    prior_low = float(prev["low"].tail(lookback).min())
    if direction == "bullish":
        return last_close > prior_high
    return last_close < prior_low


def detect_pullback_entry(
    df: pd.DataFrame,
    direction: Direction,
    atr_period: int,
    atr_multiplier: float,
    stop_type: Literal["atr", "structure"],
) -> StrategySignal | None:
    if len(df) < 30:
        return None
    recent = df.tail(15)
    impulse_high = float(recent["high"].max())
    impulse_low = float(recent["low"].min())
    midpoint = (impulse_high + impulse_low) / 2.0
    last = df.iloc[-1]
    price = float(last["close"])
    atr = calculate_atr(df, period=atr_period)

    if direction == "bullish" and not (midpoint <= price <= impulse_high):
        return None
    if direction == "bearish" and not (impulse_low <= price <= midpoint):
        return None

    structure_stop = impulse_low if direction == "bullish" else impulse_high
    atr_stop = price - atr * atr_multiplier if direction == "bullish" else price + atr * atr_multiplier
    selected_stop = atr_stop if stop_type == "atr" else structure_stop
    return StrategySignal(
        side="buy" if direction == "bullish" else "sell",
        entry=price,
        stop_loss=float(selected_stop),
        structure_stop=float(structure_stop),
        atr_stop=float(atr_stop),
        reasons=["liquidity_sweep", "break_of_structure", "pullback_entry"],
    )
