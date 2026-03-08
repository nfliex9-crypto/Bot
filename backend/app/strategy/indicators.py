"""Technical indicators used across strategies."""

import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()
    k = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(window=d_period).mean()
    return k, d


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """Identify swing high points where high is the highest in lookback window."""
    highs = df["high"]
    swing_highs = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = highs.iloc[i - lookback: i + lookback + 1]
        if highs.iloc[i] == window.max():
            swing_highs.iloc[i] = True
    return swing_highs


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """Identify swing low points where low is the lowest in lookback window."""
    lows = df["low"]
    swing_lows = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = lows.iloc[i - lookback: i + lookback + 1]
        if lows.iloc[i] == window.min():
            swing_lows.iloc[i] = True
    return swing_lows


def calculate_volume_profile(df: pd.DataFrame, bins: int = 50) -> pd.DataFrame:
    """Calculate volume profile showing volume at each price level."""
    price_range = np.linspace(df["low"].min(), df["high"].max(), bins + 1)
    volume_at_price = np.zeros(bins)

    for _, row in df.iterrows():
        for j in range(bins):
            if row["low"] <= price_range[j + 1] and row["high"] >= price_range[j]:
                volume_at_price[j] += row["volume"] / bins

    return pd.DataFrame({
        "price_low": price_range[:-1],
        "price_high": price_range[1:],
        "price_mid": (price_range[:-1] + price_range[1:]) / 2,
        "volume": volume_at_price,
    })


def identify_order_blocks(df: pd.DataFrame, min_move_pct: float = 0.003) -> list:
    """Identify bullish and bearish order blocks."""
    order_blocks = []

    for i in range(2, len(df)):
        move = (df["close"].iloc[i] - df["close"].iloc[i - 1]) / df["close"].iloc[i - 1]

        if move > min_move_pct:
            if df["close"].iloc[i - 1] < df["open"].iloc[i - 1]:
                order_blocks.append({
                    "type": "bullish",
                    "index": i - 1,
                    "high": df["high"].iloc[i - 1],
                    "low": df["low"].iloc[i - 1],
                    "timestamp": df["timestamp"].iloc[i - 1] if "timestamp" in df.columns else i - 1,
                })

        elif move < -min_move_pct:
            if df["close"].iloc[i - 1] > df["open"].iloc[i - 1]:
                order_blocks.append({
                    "type": "bearish",
                    "index": i - 1,
                    "high": df["high"].iloc[i - 1],
                    "low": df["low"].iloc[i - 1],
                    "timestamp": df["timestamp"].iloc[i - 1] if "timestamp" in df.columns else i - 1,
                })

    return order_blocks
