import numpy as np
import pandas as pd


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean().fillna(method="bfill")


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def market_bias_h1(df_h1: pd.DataFrame) -> str:
    fast = ema(df_h1["close"], 20)
    slow = ema(df_h1["close"], 50)
    if fast.iloc[-1] > slow.iloc[-1]:
        return "bullish"
    if fast.iloc[-1] < slow.iloc[-1]:
        return "bearish"
    return "neutral"


def detect_swing_points(df: pd.DataFrame, lookback: int = 3) -> tuple[pd.Series, pd.Series]:
    highs = pd.Series(False, index=df.index)
    lows = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        if df["high"].iloc[i] == df["high"].iloc[i - lookback : i + lookback + 1].max():
            highs.iloc[i] = True
        if df["low"].iloc[i] == df["low"].iloc[i - lookback : i + lookback + 1].min():
            lows.iloc[i] = True
    return highs, lows


def last_structure_levels(df: pd.DataFrame) -> tuple[float | None, float | None]:
    swing_highs, swing_lows = detect_swing_points(df)
    high_levels = df.loc[swing_highs, "high"]
    low_levels = df.loc[swing_lows, "low"]
    last_high = float(high_levels.iloc[-1]) if not high_levels.empty else None
    last_low = float(low_levels.iloc[-1]) if not low_levels.empty else None
    return last_high, last_low


def volatility_regime(df: pd.DataFrame) -> float:
    returns = df["close"].pct_change().dropna()
    if returns.empty:
        return 0.0
    return float(np.sqrt(252) * returns.std())

