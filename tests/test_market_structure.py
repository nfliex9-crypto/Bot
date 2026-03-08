import numpy as np
import pandas as pd
import pytest

from app.analysis.market_structure import Bias, analyse_structure


def _make_trending_df(direction: str = "up", n: int = 200) -> pd.DataFrame:
    """Generate trending data with clear swing highs/lows via a zigzag pattern."""
    rng = np.random.RandomState(42)
    close = np.zeros(n)
    close[0] = 100.0

    # Build a zigzag trend: up-legs are bigger than down-legs for uptrend
    wave_len = 15
    for i in range(1, n):
        phase = (i % (wave_len * 2)) < wave_len
        if direction == "up":
            step = 0.4 if phase else -0.2
        else:
            step = -0.4 if phase else 0.2
        close[i] = close[i - 1] + step + rng.normal(0, 0.05)

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open": close + rng.normal(0, 0.05, n),
        "high": close + abs(rng.normal(0.15, 0.1, n)),
        "low": close - abs(rng.normal(0.15, 0.1, n)),
        "close": close,
        "volume": rng.randint(100, 5000, n).astype(float),
    })


def test_bullish_bias():
    df = _make_trending_df("up")
    result = analyse_structure(df, lookback=5)
    assert result.bias == Bias.BULLISH
    assert len(result.swing_points) > 0


def test_bearish_bias():
    df = _make_trending_df("down")
    result = analyse_structure(df, lookback=5)
    assert result.bias == Bias.BEARISH


def test_structure_breaks_detected():
    df = _make_trending_df("up", 300)
    result = analyse_structure(df, lookback=5)
    assert len(result.structure_breaks) > 0
