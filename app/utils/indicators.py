"""
Technical indicators for strategy analysis.
All functions operate on pandas DataFrames with OHLCV columns.
"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    high = df["high"]
    low = df["low"]
    close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.ewm(span=period, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_sma(df: pd.DataFrame, period: int, column: str = "close") -> pd.Series:
    """Simple Moving Average."""
    return df[column].rolling(window=period).mean()


def calculate_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Upper band, middle band, lower band."""
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def calculate_vwap(df: pd.DataFrame, period: int = 30) -> pd.Series:
    """Rolling VWAP."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical_price * df["volume"].fillna(0.0)
    volume = df["volume"].rolling(period).sum().replace(0, np.nan)
    return pv.rolling(period).sum() / volume


def find_swing_highs(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Identify swing highs. A swing high is a candle where 'high' is the
    highest in the window of `lookback` candles on both sides.
    """
    highs = df["high"]
    swing = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = highs.iloc[i - lookback: i + lookback + 1]
        if highs.iloc[i] == window.max():
            swing.iloc[i] = True
    return swing


def find_swing_lows(df: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    Identify swing lows. A swing low is a candle where 'low' is the
    lowest in the window of `lookback` candles on both sides.
    """
    lows = df["low"]
    swing = pd.Series(False, index=df.index)
    for i in range(lookback, len(df) - lookback):
        window = lows.iloc[i - lookback: i + lookback + 1]
        if lows.iloc[i] == window.min():
            swing.iloc[i] = True
    return swing


def find_order_blocks(
    df: pd.DataFrame,
    direction: str = "bullish",
    lookback: int = 20,
) -> pd.DataFrame:
    """
    Order blocks: last bullish/bearish candle before a strong move.
    Returns a DataFrame with order block levels.
    """
    obs = []
    for i in range(1, min(lookback, len(df) - 1)):
        idx = len(df) - 1 - i
        candle = df.iloc[idx]
        prev = df.iloc[idx - 1] if idx > 0 else None

        if direction == "bullish":
            # Bullish OB: last bearish candle before strong bullish move
            if candle["close"] < candle["open"]:  # bearish candle
                next_move = df.iloc[idx + 1]["close"] - df.iloc[idx + 1]["open"]
                if next_move > 0:
                    obs.append({
                        "index": idx,
                        "top": candle["open"],
                        "bottom": candle["close"],
                        "mid": (candle["open"] + candle["close"]) / 2,
                        "type": "bullish_ob",
                    })
        elif direction == "bearish":
            # Bearish OB: last bullish candle before strong bearish move
            if candle["close"] > candle["open"]:  # bullish candle
                next_move = df.iloc[idx + 1]["close"] - df.iloc[idx + 1]["open"]
                if next_move < 0:
                    obs.append({
                        "index": idx,
                        "top": candle["close"],
                        "bottom": candle["open"],
                        "mid": (candle["open"] + candle["close"]) / 2,
                        "type": "bearish_ob",
                    })

    return pd.DataFrame(obs) if obs else pd.DataFrame()


def find_fair_value_gaps(
    df: pd.DataFrame,
    min_gap_atr_ratio: float = 0.5,
) -> pd.DataFrame:
    """
    Fair Value Gaps (FVG): Imbalance between 3-candle sequences.
    Bullish FVG: low[i+1] > high[i-1]
    Bearish FVG: high[i+1] < low[i-1]
    """
    atr = calculate_atr(df, 14)
    fvgs = []

    for i in range(1, len(df) - 1):
        gap_low = df.iloc[i - 1]["high"]
        gap_high = df.iloc[i + 1]["low"]
        min_gap = atr.iloc[i] * min_gap_atr_ratio

        # Bullish FVG
        if gap_high > gap_low and (gap_high - gap_low) >= min_gap:
            fvgs.append({
                "index": i,
                "type": "bullish_fvg",
                "top": gap_high,
                "bottom": gap_low,
                "mid": (gap_high + gap_low) / 2,
            })

        # Bearish FVG
        gap_high2 = df.iloc[i - 1]["low"]
        gap_low2 = df.iloc[i + 1]["high"]
        if gap_low2 < gap_high2 and (gap_high2 - gap_low2) >= min_gap:
            fvgs.append({
                "index": i,
                "type": "bearish_fvg",
                "top": gap_high2,
                "bottom": gap_low2,
                "mid": (gap_high2 + gap_low2) / 2,
            })

    return pd.DataFrame(fvgs) if fvgs else pd.DataFrame()


def calculate_momentum(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Price momentum."""
    return df["close"].diff(period)


def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """Simple volume profile."""
    price_range = df["high"].max() - df["low"].min()
    bin_size = price_range / bins
    levels = []

    for i in range(bins):
        price_low = df["low"].min() + i * bin_size
        price_high = price_low + bin_size
        mask = (df["close"] >= price_low) & (df["close"] < price_high)
        vol = df.loc[mask, "volume"].sum() if "volume" in df.columns else 0
        levels.append({"price_level": (price_low + price_high) / 2, "volume": vol})

    return pd.DataFrame(levels)


def calculate_support_resistance(
    df: pd.DataFrame,
    lookback: int = 20,
    tolerance: float = 0.001,
) -> dict:
    """
    Find key support and resistance levels from swing highs/lows.
    """
    swing_h = find_swing_highs(df, lookback // 4)
    swing_l = find_swing_lows(df, lookback // 4)

    resistance_levels = df.loc[swing_h, "high"].values[-5:] if swing_h.any() else []
    support_levels = df.loc[swing_l, "low"].values[-5:] if swing_l.any() else []

    return {
        "resistance": sorted(resistance_levels, reverse=True),
        "support": sorted(support_levels),
    }


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to dataframe in one call."""
    df = df.copy()
    df["atr"] = calculate_atr(df)
    df["rsi"] = calculate_rsi(df)
    df["ema_9"] = calculate_ema(df, 9)
    df["ema_21"] = calculate_ema(df, 21)
    df["ema_50"] = calculate_ema(df, 50)
    df["ema_200"] = calculate_ema(df, 200)
    df["sma_20"] = calculate_sma(df, 20)
    macd, macd_signal, macd_hist = calculate_macd(df)
    df["macd"] = macd
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist
    bb_upper, bb_mid, bb_lower = calculate_bollinger_bands(df)
    df["bb_upper"] = bb_upper
    df["bb_mid"] = bb_mid
    df["bb_lower"] = bb_lower
    df["vwap"] = calculate_vwap(df, 30)
    df["momentum"] = calculate_momentum(df)
    df["candle_body"] = (df["close"] - df["open"]).abs()
    df["candle_range"] = df["high"] - df["low"]
    df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
    df["is_bullish"] = df["close"] > df["open"]
    return df
