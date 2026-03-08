"""Technical indicators for strategy logic."""
import pandas as pd
import numpy as np


def atr(ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = ohlcv["high"]
    low = ohlcv["low"]
    close = ohlcv["close"]
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def detect_liquidity_zones(ohlcv: pd.DataFrame, threshold: float = 0.5) -> tuple[list[float], list[float]]:
    """Detect liquidity zones (equal highs/lows clusters)."""
    highs = ohlcv["high"].values
    lows = ohlcv["low"].values
    atr_val = atr(ohlcv, 14).iloc[-1] if len(ohlcv) >= 14 else (highs[-1] - lows[-1])
    cluster_dist = atr_val * threshold

    high_zones = []
    low_zones = []

    for h in highs[-50:]:
        if not high_zones or abs(h - high_zones[-1]) > cluster_dist:
            high_zones.append(h)
        else:
            high_zones[-1] = (high_zones[-1] + h) / 2

    for l in lows[-50:]:
        if not low_zones or abs(l - low_zones[-1]) > cluster_dist:
            low_zones.append(l)
        else:
            low_zones[-1] = (low_zones[-1] + l) / 2

    return high_zones[-5:], low_zones[-5:]


def structure_stop_level(
    structure_highs: list[float], structure_lows: list[float], direction: str, buffer_pct: float = 0.001
) -> float:
    """Get structure-based stop level."""
    if direction == "long":
        relevant = [l for l in structure_lows if l > 0]
        if not relevant:
            return 0
        level = min(relevant)
        return level * (1 - buffer_pct)
    else:
        relevant = [h for h in structure_highs if h > 0]
        if not relevant:
            return 0
        level = max(relevant)
        return level * (1 + buffer_pct)
