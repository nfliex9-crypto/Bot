from __future__ import annotations

import numpy as np
import pandas as pd


def ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
    return df.sort_index().copy()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    data = ensure_ohlcv(df)
    high_low = data["high"] - data["low"]
    high_close = (data["high"] - data["close"].shift(1)).abs()
    low_close = (data["low"] - data["close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()


def identify_swings(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    data = ensure_ohlcv(df)
    swing_highs = data["high"][
        (data["high"] > data["high"].shift(1)) & (data["high"] > data["high"].shift(-1))
    ]
    swing_lows = data["low"][
        (data["low"] < data["low"].shift(1)) & (data["low"] < data["low"].shift(-1))
    ]
    return swing_highs.dropna(), swing_lows.dropna()


def wick_ratio(candle: pd.Series) -> float:
    total_range = max(candle["high"] - candle["low"], 1e-9)
    body = abs(candle["close"] - candle["open"])
    return max(total_range - body, 0.0) / total_range


def volume_zscore(df: pd.DataFrame, lookback: int = 20) -> float:
    data = ensure_ohlcv(df)
    window = data["volume"].tail(lookback)
    if len(window) < 5:
        return 0.0
    std = float(window.std()) or 0.0
    if std == 0.0:
        return 0.0
    return float((window.iloc[-1] - window.mean()) / std)


def recent_range(df: pd.DataFrame, lookback: int = 20) -> float:
    data = ensure_ohlcv(df)
    window = data.tail(lookback)
    return float(window["high"].max() - window["low"].min())


def structure_bias(df: pd.DataFrame) -> tuple[str, float]:
    data = ensure_ohlcv(df)
    swing_highs, swing_lows = identify_swings(data.tail(80))
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "neutral", 0.0

    last_highs = swing_highs.tail(2).to_numpy()
    last_lows = swing_lows.tail(2).to_numpy()
    bullish = last_highs[-1] > last_highs[-2] and last_lows[-1] > last_lows[-2]
    bearish = last_highs[-1] < last_highs[-2] and last_lows[-1] < last_lows[-2]

    ema_fast = float(ema(data["close"], span=20).iloc[-1])
    ema_slow = float(ema(data["close"], span=50).iloc[-1])
    last_close = float(data["close"].iloc[-1])

    if bullish and last_close > ema_fast > ema_slow:
        return "bullish", 1.0
    if bearish and last_close < ema_fast < ema_slow:
        return "bearish", 1.0
    if last_close > ema_fast > ema_slow:
        return "bullish", 0.65
    if last_close < ema_fast < ema_slow:
        return "bearish", 0.65
    return "neutral", 0.25


def break_of_structure(df: pd.DataFrame) -> tuple[str, float]:
    data = ensure_ohlcv(df)
    if len(data) < 25:
        return "neutral", 0.0

    lookback = data.iloc[-13:-1]
    last_close = float(data["close"].iloc[-1])
    prior_high = float(lookback["high"].max())
    prior_low = float(lookback["low"].min())
    range_size = max(prior_high - prior_low, 1e-9)

    if last_close > prior_high:
        return "bullish", float((last_close - prior_high) / range_size)
    if last_close < prior_low:
        return "bearish", float((prior_low - last_close) / range_size)
    return "neutral", 0.0


def liquidity_sweep(df: pd.DataFrame) -> tuple[str, float, float]:
    data = ensure_ohlcv(df)
    if len(data) < 20:
        return "neutral", 0.0, 0.0

    reference = data.iloc[-2]
    history = data.iloc[-15:-2]
    recent_high = float(history["high"].max())
    recent_low = float(history["low"].min())

    if reference["low"] < recent_low and reference["close"] > recent_low:
        intensity = float((recent_low - reference["low"]) / max(recent_high - recent_low, 1e-9))
        return "bullish", max(intensity, 0.0), recent_low
    if reference["high"] > recent_high and reference["close"] < recent_high:
        intensity = float((reference["high"] - recent_high) / max(recent_high - recent_low, 1e-9))
        return "bearish", max(intensity, 0.0), recent_high
    return "neutral", 0.0, 0.0


def pullback_ready(df: pd.DataFrame, direction: str) -> tuple[bool, float]:
    data = ensure_ohlcv(df)
    if len(data) < 3:
        return False, 0.0

    trigger = data.iloc[-2]
    current = data.iloc[-1]
    midpoint = float(trigger["low"] + (trigger["high"] - trigger["low"]) * 0.5)
    tolerance = float((trigger["high"] - trigger["low"]) * 0.2)

    if direction == "bullish":
        ready = current["close"] <= midpoint + tolerance and current["close"] >= trigger["low"]
    else:
        ready = current["close"] >= midpoint - tolerance and current["close"] <= trigger["high"]
    return bool(ready), midpoint


def normalize_dataframe(rows: list[dict[str, float | int | str]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.set_index("timestamp")
    return frame.dropna()
