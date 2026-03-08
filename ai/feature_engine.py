"""
Feature engineering for the ML model.
Extracts technical and structural features from OHLCV data
to feed into the RandomForest classifier.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.indicators import atr, bollinger_bands, ema, macd, rsi, stochastic, vwap


def extract_features(
    h1: pd.DataFrame, m15: pd.DataFrame, m5: pd.DataFrame
) -> dict:
    """
    Build a flat feature dict from multi-timeframe candle data.
    Returns ~40 features for the classifier.
    """
    f = {}

    f.update(_price_features(m5, "m5"))
    f.update(_price_features(m15, "m15"))
    f.update(_price_features(h1, "h1"))

    f.update(_momentum_features(m5, "m5"))
    f.update(_momentum_features(m15, "m15"))

    f.update(_volatility_features(m5, "m5"))
    f.update(_volatility_features(h1, "h1"))

    f.update(_volume_features(m5, "m5"))
    f.update(_structure_features(m5, "m5"))

    for k, v in f.items():
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            f[k] = 0.0

    return f


def _price_features(df: pd.DataFrame, prefix: str) -> dict:
    if df.empty or len(df) < 20:
        return {f"{prefix}_ema_dist": 0, f"{prefix}_trend": 0, f"{prefix}_body_ratio": 0}

    close = df["close"]
    ema20 = ema(close, 20)
    ema50 = ema(close, 50) if len(df) >= 50 else ema20

    last = close.iloc[-1]
    return {
        f"{prefix}_ema_dist": float((last - ema20.iloc[-1]) / last) if last else 0,
        f"{prefix}_trend": float((ema20.iloc[-1] - ema50.iloc[-1]) / last) if last else 0,
        f"{prefix}_body_ratio": float(
            abs(df.iloc[-1]["close"] - df.iloc[-1]["open"]) /
            max(df.iloc[-1]["high"] - df.iloc[-1]["low"], 1e-10)
        ),
    }


def _momentum_features(df: pd.DataFrame, prefix: str) -> dict:
    if df.empty or len(df) < 26:
        return {f"{prefix}_rsi": 50, f"{prefix}_macd": 0, f"{prefix}_stoch_k": 50}

    rsi_val = rsi(df).iloc[-1]
    macd_line, signal, hist = macd(df)
    k, d = stochastic(df)

    return {
        f"{prefix}_rsi": float(rsi_val) if not np.isnan(rsi_val) else 50,
        f"{prefix}_macd": float(hist.iloc[-1]) if not np.isnan(hist.iloc[-1]) else 0,
        f"{prefix}_macd_signal": float(
            1 if macd_line.iloc[-1] > signal.iloc[-1] else -1
        ) if not np.isnan(macd_line.iloc[-1]) else 0,
        f"{prefix}_stoch_k": float(k.iloc[-1]) if not np.isnan(k.iloc[-1]) else 50,
    }


def _volatility_features(df: pd.DataFrame, prefix: str) -> dict:
    if df.empty or len(df) < 20:
        return {f"{prefix}_atr_pct": 0, f"{prefix}_bb_width": 0}

    atr_val = atr(df, 14).iloc[-1]
    mid, upper, lower = bollinger_bands(df)

    close = df.iloc[-1]["close"]
    bb_w = float((upper.iloc[-1] - lower.iloc[-1]) / close) if close and not np.isnan(upper.iloc[-1]) else 0

    return {
        f"{prefix}_atr_pct": float(atr_val / close) if close and not np.isnan(atr_val) else 0,
        f"{prefix}_bb_width": bb_w,
        f"{prefix}_bb_pos": float(
            (close - lower.iloc[-1]) / max(upper.iloc[-1] - lower.iloc[-1], 1e-10)
        ) if not np.isnan(lower.iloc[-1]) else 0.5,
    }


def _volume_features(df: pd.DataFrame, prefix: str) -> dict:
    if df.empty or len(df) < 20:
        return {f"{prefix}_vol_ratio": 1.0, f"{prefix}_vol_trend": 0}

    vol = df["volume"]
    avg_vol = vol.rolling(20).mean().iloc[-1]
    if np.isnan(avg_vol) or avg_vol == 0:
        return {f"{prefix}_vol_ratio": 1.0, f"{prefix}_vol_trend": 0}

    return {
        f"{prefix}_vol_ratio": float(vol.iloc[-1] / avg_vol),
        f"{prefix}_vol_trend": float(
            (vol.tail(5).mean() - vol.tail(20).mean()) / avg_vol
        ),
    }


def _structure_features(df: pd.DataFrame, prefix: str) -> dict:
    if df.empty or len(df) < 10:
        return {
            f"{prefix}_higher_highs": 0, f"{prefix}_lower_lows": 0,
            f"{prefix}_range_pct": 0,
        }

    recent = df.tail(20)
    highs = recent["high"].values
    lows = recent["low"].values

    hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1])
    ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1])
    price_range = (recent["high"].max() - recent["low"].min()) / recent["close"].iloc[-1]

    return {
        f"{prefix}_higher_highs": hh_count,
        f"{prefix}_lower_lows": ll_count,
        f"{prefix}_range_pct": float(price_range),
    }
