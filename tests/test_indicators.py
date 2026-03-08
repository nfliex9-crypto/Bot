import numpy as np
import pandas as pd
import pytest

from app.analysis.indicators import atr, ema, rsi, sma, swing_highs, swing_lows


def _make_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.RandomState(42)
    close = np.cumsum(rng.normal(0, 0.5, n)) + 100
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="5min"),
        "open": close + rng.normal(0, 0.1, n),
        "high": close + abs(rng.normal(0, 0.3, n)),
        "low": close - abs(rng.normal(0, 0.3, n)),
        "close": close,
        "volume": rng.randint(100, 5000, n).astype(float),
    })


def test_atr_returns_series():
    df = _make_df()
    result = atr(df, 14)
    assert isinstance(result, pd.Series)
    assert len(result) == len(df)
    assert result.iloc[-1] > 0


def test_ema_sma_shape():
    df = _make_df()
    e = ema(df["close"], 21)
    s = sma(df["close"], 21)
    assert len(e) == len(df)
    assert len(s) == len(df)


def test_rsi_bounds():
    df = _make_df()
    r = rsi(df["close"], 14)
    valid = r.dropna()
    assert valid.min() >= 0
    assert valid.max() <= 100


def test_swing_points():
    df = _make_df(200)
    sh = swing_highs(df, 5)
    sl = swing_lows(df, 5)
    assert sh.sum() > 0
    assert sl.sum() > 0
