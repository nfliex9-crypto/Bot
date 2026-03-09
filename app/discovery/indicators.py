"""
Comprehensive indicator computation for strategy discovery.

Pre-computes all indicator variants that any generated strategy might
reference, using standardised column naming conventions:

    ema_{period}        sma_{period}        rsi_{period}
    atr_{period}        momentum_{period}
    macd_{f}_{s}_{sig}  macd_signal_{f}_{s}_{sig}  macd_hist_{f}_{s}_{sig}
    bb_upper_{p}_{s10}  bb_mid_{p}_{s10}  bb_lower_{p}_{s10}  bb_width_{p}_{s10}
    vwap                highest_{period}    lowest_{period}
"""
import numpy as np
import pandas as pd

from app.utils.indicators import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)

EMA_PERIODS = [5, 8, 9, 10, 13, 20, 21, 30, 50, 100, 200]
SMA_PERIODS = [5, 10, 20, 50, 100, 200]
RSI_PERIODS = [7, 9, 14, 21]
ATR_PERIODS = [7, 10, 14, 20]
MOMENTUM_PERIODS = [5, 10, 14, 20]
MACD_CONFIGS = [(8, 21, 5), (12, 26, 9), (5, 13, 4)]
BB_CONFIGS = [
    (14, 1.5), (14, 2.0),
    (20, 1.5), (20, 2.0), (20, 2.5),
    (30, 2.0), (30, 2.5),
]
HIGHEST_LOWEST_PERIODS = [5, 10, 14, 20, 30, 50]
VWAP_PERIOD = 20


def bb_col(kind: str, period: int, std: float) -> str:
    return f"bb_{kind}_{period}_{int(std * 10)}"


def add_all_discovery_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add every indicator variant to *df* (in-place copy returned)."""
    df = df.copy()

    for p in EMA_PERIODS:
        if len(df) >= p:
            df[f"ema_{p}"] = calculate_ema(df, p)
    for p in SMA_PERIODS:
        if len(df) >= p:
            df[f"sma_{p}"] = calculate_sma(df, p)
    for p in RSI_PERIODS:
        if len(df) >= p:
            df[f"rsi_{p}"] = calculate_rsi(df, p)
    for p in ATR_PERIODS:
        if len(df) >= p:
            df[f"atr_{p}"] = calculate_atr(df, p)
    for p in MOMENTUM_PERIODS:
        df[f"momentum_{p}"] = df["close"].diff(p)

    for fast, slow, sig in MACD_CONFIGS:
        if len(df) >= slow:
            ml, sl, hist = calculate_macd(df, fast, slow, sig)
            tag = f"{fast}_{slow}_{sig}"
            df[f"macd_{tag}"] = ml
            df[f"macd_signal_{tag}"] = sl
            df[f"macd_hist_{tag}"] = hist

    for period, std in BB_CONFIGS:
        if len(df) >= period:
            upper, mid, lower = calculate_bollinger_bands(df, period, std)
            df[bb_col("upper", period, std)] = upper
            df[bb_col("mid", period, std)] = mid
            df[bb_col("lower", period, std)] = lower
            df[bb_col("width", period, std)] = (upper - lower) / mid.replace(0, np.nan)

    for p in HIGHEST_LOWEST_PERIODS:
        df[f"highest_{p}"] = df["high"].shift(1).rolling(p).max()
        df[f"lowest_{p}"] = df["low"].shift(1).rolling(p).min()

    if "volume" in df.columns:
        tp = (df["high"] + df["low"] + df["close"]) / 3.0
        cum_tpv = (tp * df["volume"]).rolling(VWAP_PERIOD).sum()
        cum_vol = df["volume"].rolling(VWAP_PERIOD).sum().replace(0, np.nan)
        df["vwap"] = cum_tpv / cum_vol

    df["candle_body"] = (df["close"] - df["open"]).abs()
    df["candle_range"] = df["high"] - df["low"]
    df["is_bullish"] = (df["close"] > df["open"]).astype(int)

    return df
