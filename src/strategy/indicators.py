"""
Technical indicator calculations using pandas.
Pure numpy/pandas - no external TA library dependency issues.
"""

import pandas as pd
import numpy as np
from typing import Tuple


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    return tr.ewm(span=period, adjust=False).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, std_dev: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = calculate_sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Identify swing highs: bars where high is the highest within ±lookback bars.
    Returns boolean Series.
    """
    highs = df["high"]
    result = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = highs.iloc[i - lookback: i + lookback + 1]
        if highs.iloc[i] == window.max():
            result.iloc[i] = True
    return result


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Identify swing lows: bars where low is the lowest within ±lookback bars.
    Returns boolean Series.
    """
    lows = df["low"]
    result = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = lows.iloc[i - lookback: i + lookback + 1]
        if lows.iloc[i] == window.min():
            result.iloc[i] = True
    return result


def identify_order_blocks(df: pd.DataFrame, lookback: int = 3) -> pd.DataFrame:
    """
    Identify bullish and bearish order blocks.
    Bullish OB: last bearish candle before a strong bullish move.
    Bearish OB: last bullish candle before a strong bearish move.
    """
    df = df.copy()
    df["bullish_ob"] = False
    df["bearish_ob"] = False
    df["ob_high"] = np.nan
    df["ob_low"] = np.nan

    for i in range(lookback, len(df) - lookback):
        # Bullish OB: bearish candle followed by bullish impulse
        if df["close"].iloc[i] < df["open"].iloc[i]:
            future_closes = df["close"].iloc[i + 1: i + lookback + 1]
            if len(future_closes) > 0 and future_closes.max() > df["high"].iloc[i] * 1.002:
                df.at[df.index[i], "bullish_ob"] = True
                df.at[df.index[i], "ob_high"] = df["high"].iloc[i]
                df.at[df.index[i], "ob_low"] = df["low"].iloc[i]

        # Bearish OB: bullish candle followed by bearish impulse
        if df["close"].iloc[i] > df["open"].iloc[i]:
            future_closes = df["close"].iloc[i + 1: i + lookback + 1]
            if len(future_closes) > 0 and future_closes.min() < df["low"].iloc[i] * 0.998:
                df.at[df.index[i], "bearish_ob"] = True
                df.at[df.index[i], "ob_high"] = df["high"].iloc[i]
                df.at[df.index[i], "ob_low"] = df["low"].iloc[i]

    return df


def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Simple volume-at-price profile."""
    price_range = df["close"].max() - df["close"].min()
    if price_range == 0:
        return pd.DataFrame()
    bin_size = price_range / bins
    df_copy = df.copy()
    df_copy["price_bin"] = ((df_copy["close"] - df_copy["close"].min()) / bin_size).astype(int)
    profile = df_copy.groupby("price_bin").agg(
        volume=("volume", "sum"),
        price=("close", "mean"),
    ).reset_index()
    return profile
