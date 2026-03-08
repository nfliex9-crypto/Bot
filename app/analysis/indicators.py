from __future__ import annotations

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=1).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """Boolean mask of swing highs."""
    high = df["high"]
    mask = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = high.iloc[i - lookback : i + lookback + 1]
        if high.iloc[i] == window.max():
            mask.iloc[i] = True
    return mask


def swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """Boolean mask of swing lows."""
    low = df["low"]
    mask = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = low.iloc[i - lookback : i + lookback + 1]
        if low.iloc[i] == window.min():
            mask.iloc[i] = True
    return mask


def detect_order_blocks(df: pd.DataFrame, lookback: int = 20) -> list[dict]:
    """Detect bullish and bearish order blocks from recent price action."""
    blocks: list[dict] = []
    if len(df) < lookback + 2:
        return blocks

    recent = df.iloc[-lookback:].reset_index(drop=True)

    for i in range(1, len(recent) - 1):
        body_prev = abs(recent["close"].iloc[i - 1] - recent["open"].iloc[i - 1])
        body_curr = abs(recent["close"].iloc[i] - recent["open"].iloc[i])

        if body_curr > body_prev * 2:
            if recent["close"].iloc[i] > recent["open"].iloc[i]:
                blocks.append(
                    {
                        "type": "bullish",
                        "high": recent["high"].iloc[i - 1],
                        "low": recent["low"].iloc[i - 1],
                        "timestamp": recent["timestamp"].iloc[i - 1],
                    }
                )
            elif recent["close"].iloc[i] < recent["open"].iloc[i]:
                blocks.append(
                    {
                        "type": "bearish",
                        "high": recent["high"].iloc[i - 1],
                        "low": recent["low"].iloc[i - 1],
                        "timestamp": recent["timestamp"].iloc[i - 1],
                    }
                )

    return blocks


def volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Simple volume-at-price profile."""
    price_range = np.linspace(df["low"].min(), df["high"].max(), bins + 1)
    result = []
    for i in range(len(price_range) - 1):
        lo, hi = price_range[i], price_range[i + 1]
        mask = (df["close"] >= lo) & (df["close"] < hi)
        vol = df.loc[mask, "volume"].sum()
        result.append({"price_low": lo, "price_high": hi, "volume": vol})
    return pd.DataFrame(result)
