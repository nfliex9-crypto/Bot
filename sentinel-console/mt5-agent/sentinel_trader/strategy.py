"""Deterministic long/short rules from closed M15/H1 MT5 broker bars.

No external network, no strategy training and no permission to place orders.
These rules are *research baselines*, not validated profitable algorithms.
"""
from __future__ import annotations
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Signal:
    symbol: str
    family: str
    side: int  # 1 buy, -1 sell
    bar_time: int
    atr: float
    stop_atr: float = 1.5
    reward_r: float = 2.0


def ema(values: list[float], length: int) -> float:
    if len(values) < length or any(not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError("INSUFFICIENT_OR_INVALID_CLOSES")
    alpha = 2.0 / (length + 1)
    result = sum(values[:length]) / length
    for value in values[length:]:
        result += alpha * (value - result)
    return result


def atr(bars: list[dict], length: int = 14) -> float:
    if len(bars) < length + 1:
        raise ValueError("INSUFFICIENT_ATR_BARS")
    true_ranges = []
    for before, bar in zip(bars[:-1], bars[1:]):
        h, l, prev = float(bar["high"]), float(bar["low"]), float(before["close"])
        if not all(math.isfinite(v) and v > 0 for v in (h, l, prev)) or h < l:
            raise ValueError("INVALID_ATR_SOURCE")
        true_ranges.append(max(h - l, abs(h - prev), abs(l - prev)))
    return sum(true_ranges[-length:]) / length


def decide(symbol: str, m15: list[dict], h1: list[dict]) -> Signal | None:
    if len(m15) < 110 or len(h1) < 90:
        return None
    if any(int(a["time"]) >= int(b["time"]) for a, b in zip(m15[:-1], m15[1:])):
        raise ValueError("UNSORTED_OR_DUPLICATE_M15")
    if any(int(a["time"]) >= int(b["time"]) for a, b in zip(h1[:-1], h1[1:])):
        raise ValueError("UNSORTED_OR_DUPLICATE_H1")
    prices = [float(b["close"]) for b in m15]
    hours = [float(b["close"]) for b in h1]
    m_fast, m_slow = ema(prices, 20), ema(prices, 50)
    h_fast, h_slow = ema(hours, 20), ema(hours, 50)
    volatility = atr(m15)
    if not math.isfinite(volatility) or volatility <= 0:
        return None
    prev_fast = ema(prices[:-1], 20)
    prev, latest = m15[-2], m15[-1]
    side = 1 if m_fast > m_slow and h_fast > h_slow else (-1 if m_fast < m_slow and h_fast < h_slow else 0)
    if not side:
        return None
    # Closed-bar pullback reclaim in the direction of M15 and H1 momentum.
    if side == 1 and float(prev["close"]) <= prev_fast and float(latest["close"]) > m_fast:
        return Signal(symbol, "trend_pullback", side, int(latest["time"]), volatility)
    if side == -1 and float(prev["close"]) >= prev_fast and float(latest["close"]) < m_fast:
        return Signal(symbol, "trend_pullback", side, int(latest["time"]), volatility)
    # Donchian close breakout. Excludes current candle from the lookback.
    history = m15[-21:-1]
    if side == 1 and float(latest["close"]) > max(float(b["high"]) for b in history):
        return Signal(symbol, "donchian_breakout", side, int(latest["time"]), volatility)
    if side == -1 and float(latest["close"]) < min(float(b["low"]) for b in history):
        return Signal(symbol, "donchian_breakout", side, int(latest["time"]), volatility)
    return None
