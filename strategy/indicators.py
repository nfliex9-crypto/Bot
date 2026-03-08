"""
Technical indicators used by the strategy engine.
All computations use vectorized pandas/numpy operations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Simple volume profile: group volume by price bins."""
    price_range = np.linspace(df["low"].min(), df["high"].max(), bins + 1)
    mid = (price_range[:-1] + price_range[1:]) / 2
    vol = np.zeros(bins)
    for _, row in df.iterrows():
        for j in range(bins):
            if price_range[j] <= row["close"] <= price_range[j + 1]:
                vol[j] += row["volume"]
                break
    return pd.DataFrame({"price": mid, "volume": vol})


def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0):
    mid = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    return mid, mid + std_dev * std, mid - std_dev * std


def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = ema(df["close"], fast)
    slow_ema = ema(df["close"], slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()
    return k, d


def vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    return (typical * df["volume"]).cumsum() / df["volume"].cumsum()


def order_block_detector(df: pd.DataFrame, lookback: int = 10) -> list:
    """
    Identify potential order blocks: strong candles followed by
    displacement moves.
    """
    obs = []
    if len(df) < lookback + 2:
        return obs

    for i in range(lookback, len(df) - 1):
        body = abs(df.iloc[i]["close"] - df.iloc[i]["open"])
        candle_range = df.iloc[i]["high"] - df.iloc[i]["low"]
        if candle_range == 0:
            continue

        body_ratio = body / candle_range

        if body_ratio > 0.6:
            next_body = abs(df.iloc[i + 1]["close"] - df.iloc[i + 1]["open"])
            if next_body > body * 1.5:
                is_bullish = df.iloc[i + 1]["close"] > df.iloc[i + 1]["open"]
                obs.append({
                    "index": i,
                    "timestamp": df.iloc[i]["timestamp"],
                    "high": float(df.iloc[i]["high"]),
                    "low": float(df.iloc[i]["low"]),
                    "type": "bullish_ob" if is_bullish else "bearish_ob",
                })

    return obs
