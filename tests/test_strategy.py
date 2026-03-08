import numpy as np
import pandas as pd
import pytest

from app.strategy.liquidity_sweep import detect_liquidity_sweep
from app.strategy.pullback_entry import find_pullback_entry


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


def test_liquidity_sweep_returns_list():
    df = _make_df(200)
    sweeps = detect_liquidity_sweep(df)
    assert isinstance(sweeps, list)


def test_pullback_entry_returns_none_or_dict():
    df = _make_df(100)
    result = find_pullback_entry(df, "long")
    assert result is None or isinstance(result, dict)


def test_pullback_entry_short():
    df = _make_df(100)
    result = find_pullback_entry(df, "short")
    assert result is None or isinstance(result, dict)
