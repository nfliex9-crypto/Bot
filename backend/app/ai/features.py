"""
Feature Engineering for the AI Classifier

Extracts a rich feature vector from OHLCV data to feed the Random Forest model.
Features include technical indicators, market structure context, and pattern metrics.
"""

import numpy as np
import pandas as pd
from typing import Optional


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b != 0 else default


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(high - low), (high - close).abs(), (low - close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std * std_dev
    lower = mid - std * std_dev
    return upper, mid, lower


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def extract_features(
    df: pd.DataFrame,
    signal_context: Optional[dict] = None,
) -> Optional[np.ndarray]:
    """
    Extract feature vector from OHLCV DataFrame and optional signal context.

    Parameters
    ----------
    df : OHLCV DataFrame (at least 50 bars)
    signal_context : dict with keys like setup_quality, rsi, fvg_detected, etc.

    Returns
    -------
    1D numpy array of features, or None if data insufficient
    """
    if df is None or len(df) < 50:
        return None

    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Price action
    body = (close - df["open"]).abs()
    candle_range = high - low
    body_ratio = (body / candle_range.replace(0, np.nan)).fillna(0)
    upper_wick = high - pd.concat([close, df["open"]], axis=1).max(axis=1)
    lower_wick = pd.concat([close, df["open"]], axis=1).min(axis=1) - low
    upper_wick_ratio = (upper_wick / candle_range.replace(0, np.nan)).fillna(0)
    lower_wick_ratio = (lower_wick / candle_range.replace(0, np.nan)).fillna(0)

    # ATR normalised values
    atr_val = atr(df)
    atr_now = atr_val.iloc[-1]
    atr_norm = safe_divide(atr_now, close.iloc[-1])

    # RSI
    rsi_14 = rsi(close)
    rsi_7 = rsi(close, 7)
    rsi_val = rsi_14.iloc[-1]
    rsi_7_val = rsi_7.iloc[-1]

    # EMAs
    ema_8 = ema(close, 8)
    ema_21 = ema(close, 21)
    ema_50 = ema(close, 50)

    price_vs_ema8 = safe_divide(close.iloc[-1] - ema_8.iloc[-1], atr_now)
    price_vs_ema21 = safe_divide(close.iloc[-1] - ema_21.iloc[-1], atr_now)
    price_vs_ema50 = safe_divide(close.iloc[-1] - ema_50.iloc[-1], atr_now)
    ema8_vs_21 = safe_divide(ema_8.iloc[-1] - ema_21.iloc[-1], atr_now)
    ema21_vs_50 = safe_divide(ema_21.iloc[-1] - ema_50.iloc[-1], atr_now)

    # MACD
    macd_line, signal_line, hist = macd(close)
    macd_norm = safe_divide(macd_line.iloc[-1], atr_now)
    macd_hist_norm = safe_divide(hist.iloc[-1], atr_now)

    # Bollinger Bands
    bb_upper, bb_mid, bb_lower = bollinger_bands(close)
    bb_width = safe_divide(bb_upper.iloc[-1] - bb_lower.iloc[-1], bb_mid.iloc[-1])
    bb_position = safe_divide(
        close.iloc[-1] - bb_lower.iloc[-1],
        bb_upper.iloc[-1] - bb_lower.iloc[-1]
    )

    # Volume analysis (last 5 bars vs 20-bar avg)
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]
    vol_ratio = safe_divide(volume.iloc[-1], vol_avg_20)
    vol_trend = safe_divide(
        volume.iloc[-5:].mean() - volume.iloc[-25:-5].mean(),
        volume.iloc[-25:-5].mean()
    )

    # Recent candle statistics (last 5 bars)
    last5 = df.iloc[-5:]
    avg_body_ratio_5 = body_ratio.iloc[-5:].mean()
    avg_upper_wick_5 = upper_wick_ratio.iloc[-5:].mean()
    avg_lower_wick_5 = lower_wick_ratio.iloc[-5:].mean()

    # Price momentum
    momentum_1 = safe_divide(close.iloc[-1] - close.iloc[-2], atr_now)
    momentum_3 = safe_divide(close.iloc[-1] - close.iloc[-4], atr_now)
    momentum_5 = safe_divide(close.iloc[-1] - close.iloc[-6], atr_now)

    # Volatility regime
    atr_20_avg = atr_val.rolling(20).mean().iloc[-1]
    volatility_ratio = safe_divide(atr_now, atr_20_avg)

    # High/Low position over 20 bars
    high_20 = high.iloc[-20:].max()
    low_20 = low.iloc[-20:].min()
    range_20 = high_20 - low_20
    price_in_range = safe_divide(close.iloc[-1] - low_20, range_20)

    features = np.array([
        # RSI (2)
        rsi_val,
        rsi_7_val,
        # EMA relationships (5)
        price_vs_ema8,
        price_vs_ema21,
        price_vs_ema50,
        ema8_vs_21,
        ema21_vs_50,
        # MACD (2)
        macd_norm,
        macd_hist_norm,
        # Bollinger (2)
        bb_width,
        bb_position,
        # ATR (1)
        atr_norm,
        # Volume (2)
        vol_ratio,
        vol_trend,
        # Price action (5)
        avg_body_ratio_5,
        avg_upper_wick_5,
        avg_lower_wick_5,
        body_ratio.iloc[-1],
        candle_range.iloc[-1] / atr_now if atr_now else 0,
        # Momentum (3)
        momentum_1,
        momentum_3,
        momentum_5,
        # Volatility (1)
        volatility_ratio,
        # Range position (1)
        price_in_range,
    ], dtype=np.float32)

    # Append signal context features if available
    context_features = np.zeros(6, dtype=np.float32)
    if signal_context:
        context_features[0] = float(signal_context.get("setup_quality", 0.5))
        context_features[1] = float(signal_context.get("rsi", 50)) / 100.0
        context_features[2] = 1.0 if signal_context.get("fvg_detected") else 0.0
        context_features[3] = 1.0 if signal_context.get("order_block_level") else 0.0
        context_features[4] = float(signal_context.get("rr_ratio_tp1", 1.5)) / 5.0
        context_features[5] = 1.0 if signal_context.get("volume_spike") else 0.0

    features = np.concatenate([features, context_features])

    # Replace any NaN/Inf
    features = np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
    return features


def get_feature_names() -> list:
    base = [
        "rsi_14", "rsi_7",
        "price_vs_ema8", "price_vs_ema21", "price_vs_ema50",
        "ema8_vs_21", "ema21_vs_50",
        "macd_norm", "macd_hist_norm",
        "bb_width", "bb_position",
        "atr_norm",
        "vol_ratio", "vol_trend",
        "avg_body_ratio_5", "avg_upper_wick_5", "avg_lower_wick_5",
        "last_body_ratio", "last_candle_size",
        "momentum_1", "momentum_3", "momentum_5",
        "volatility_ratio", "price_in_range",
    ]
    context = [
        "setup_quality", "rsi_norm", "fvg_detected",
        "order_block", "rr_ratio_norm", "volume_spike",
    ]
    return base + context
