from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .domain import MarketSnapshot, MarketType, TradeDirection, TradeSignal


def _ensure_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required OHLCV columns: {sorted(missing)}")
    return frame.sort_index().copy()


def calculate_atr(frame: pd.DataFrame, period: int = 14) -> float:
    frame = _ensure_dataframe(frame)
    high_low = frame["high"] - frame["low"]
    high_close = (frame["high"] - frame["close"].shift()).abs()
    low_close = (frame["low"] - frame["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(period).mean().iloc[-1]
    return float(atr if pd.notna(atr) else true_range.tail(period).mean())


def extract_swings(frame: pd.DataFrame, lookback: int = 2) -> tuple[pd.Series, pd.Series]:
    frame = _ensure_dataframe(frame)
    highs = frame["high"]
    lows = frame["low"]

    swing_high = highs[(highs.shift(lookback) < highs) & (highs.shift(-lookback) < highs)]
    swing_low = lows[(lows.shift(lookback) > lows) & (lows.shift(-lookback) > lows)]
    return swing_high.dropna(), swing_low.dropna()


def determine_h1_bias(frame: pd.DataFrame) -> str:
    frame = _ensure_dataframe(frame)
    ema_fast = frame["close"].ewm(span=20).mean()
    ema_slow = frame["close"].ewm(span=50).mean()
    swing_highs, swing_lows = extract_swings(frame.tail(120))

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        higher_highs = swing_highs.iloc[-1] > swing_highs.iloc[-2]
        higher_lows = swing_lows.iloc[-1] > swing_lows.iloc[-2]
        lower_highs = swing_highs.iloc[-1] < swing_highs.iloc[-2]
        lower_lows = swing_lows.iloc[-1] < swing_lows.iloc[-2]
    else:
        higher_highs = frame["close"].iloc[-1] > frame["close"].iloc[-10]
        higher_lows = frame["low"].tail(10).min() > frame["low"].tail(30).min()
        lower_highs = frame["close"].iloc[-1] < frame["close"].iloc[-10]
        lower_lows = frame["high"].tail(10).max() < frame["high"].tail(30).max()

    last_close = frame["close"].iloc[-1]
    if last_close > ema_fast.iloc[-1] > ema_slow.iloc[-1] and higher_highs and higher_lows:
        return "bullish"
    if last_close < ema_fast.iloc[-1] < ema_slow.iloc[-1] and lower_highs and lower_lows:
        return "bearish"
    return "neutral"


def determine_m15_structure(frame: pd.DataFrame) -> str:
    frame = _ensure_dataframe(frame)
    recent_high = frame["high"].rolling(12).max().shift(1)
    recent_low = frame["low"].rolling(12).min().shift(1)
    last_close = frame["close"].iloc[-1]
    if last_close > recent_high.iloc[-1]:
        return "bullish"
    if last_close < recent_low.iloc[-1]:
        return "bearish"

    ema_fast = frame["close"].ewm(span=12).mean().iloc[-1]
    ema_slow = frame["close"].ewm(span=26).mean().iloc[-1]
    if last_close > ema_fast > ema_slow:
        return "bullish"
    if last_close < ema_fast < ema_slow:
        return "bearish"
    return "neutral"


def _build_signal(
    symbol: str,
    market: MarketType,
    direction: TradeDirection,
    session: str,
    entry: float,
    stop: float,
    atr: float,
    pullback_level: float,
    bos_level: float,
    liquidity_level: float,
    h1_bias: str,
    m15_trend: str,
) -> TradeSignal:
    risk = abs(entry - stop)
    tps = [
        entry + risk * ratio if direction == TradeDirection.LONG else entry - risk * ratio
        for ratio in (1.0, 1.5, 2.0)
    ]
    reason = (
        f"{direction.value} setup from liquidity sweep, break of structure, and pullback "
        f"with {h1_bias} H1 bias and {m15_trend} M15 structure"
    )
    features = {
        "atr": atr,
        "risk_distance": risk,
        "bos_displacement": abs(entry - bos_level),
        "pullback_depth": abs(entry - pullback_level),
        "liquidity_distance": abs(entry - liquidity_level),
        "h1_alignment": 1.0 if h1_bias == direction.value.replace("long", "bullish").replace("short", "bearish") else 0.0,
        "m15_alignment": 1.0 if m15_trend == direction.value.replace("long", "bullish").replace("short", "bearish") else 0.0,
        "session_score": 1.0 if session else 0.0,
    }
    return TradeSignal(
        symbol=symbol,
        market=market,
        direction=direction,
        entry_price=entry,
        stop_loss=stop,
        take_profit_levels=tps,
        reason=reason,
        atr=atr,
        pullback_level=pullback_level,
        bos_level=bos_level,
        liquidity_level=liquidity_level,
        h1_bias=h1_bias,
        m15_trend=m15_trend,
        session=session,
        features=features,
    )


def detect_execution_setup(
    symbol: str,
    market: MarketType,
    h1_frame: pd.DataFrame,
    m15_frame: pd.DataFrame,
    m5_frame: pd.DataFrame,
    session: str,
) -> tuple[MarketSnapshot, TradeSignal | None]:
    h1_frame = _ensure_dataframe(h1_frame)
    m15_frame = _ensure_dataframe(m15_frame)
    m5_frame = _ensure_dataframe(m5_frame)

    atr = calculate_atr(m5_frame)
    h1_bias = determine_h1_bias(h1_frame)
    m15_trend = determine_m15_structure(m15_frame)
    snapshot = MarketSnapshot(
        symbol=symbol,
        market=market,
        h1_bias=h1_bias,
        m15_structure=m15_trend,
        m5_context={},
        atr=atr,
        timestamp=datetime.now(timezone.utc),
    )

    if h1_bias == "neutral" or m15_trend == "neutral" or h1_bias != m15_trend:
        return snapshot, None

    recent = m5_frame.tail(40).reset_index(drop=True)
    direction = TradeDirection.LONG if h1_bias == "bullish" else TradeDirection.SHORT
    sweep_idx = None
    bos_idx = None
    liquidity_level = 0.0
    bos_level = 0.0
    pullback_level = 0.0

    if direction == TradeDirection.LONG:
        for idx in range(10, len(recent) - 2):
            reference_low = recent["low"].iloc[max(0, idx - 10):idx].min()
            candle = recent.iloc[idx]
            if candle["low"] < reference_low and candle["close"] > reference_low:
                sweep_idx = idx
                liquidity_level = float(reference_low)
        if sweep_idx is not None:
            bos_level = float(recent["high"].iloc[max(0, sweep_idx - 8):sweep_idx].max())
            for idx in range(sweep_idx + 1, len(recent)):
                candle = recent.iloc[idx]
                body = candle["close"] - candle["open"]
                if candle["close"] > bos_level and body > (0.35 * atr):
                    bos_idx = idx
                    break
        if bos_idx is None:
            return snapshot, None

        impulse_high = float(recent["high"].iloc[bos_idx])
        sweep_low = float(recent["low"].iloc[sweep_idx])
        pullback_level = impulse_high - ((impulse_high - sweep_low) * 0.5)
        last_close = float(recent["close"].iloc[-1])
        last_low = float(recent["low"].iloc[-1])
        last_high = float(recent["high"].iloc[-1])
        touched_pullback = (last_low <= pullback_level <= last_high) or abs(last_close - pullback_level) <= atr * 0.2
        if not touched_pullback or last_close < bos_level:
            return snapshot, None
        entry = last_close
        stop = sweep_low - (atr * 0.25)
    else:
        for idx in range(10, len(recent) - 2):
            reference_high = recent["high"].iloc[max(0, idx - 10):idx].max()
            candle = recent.iloc[idx]
            if candle["high"] > reference_high and candle["close"] < reference_high:
                sweep_idx = idx
                liquidity_level = float(reference_high)
        if sweep_idx is not None:
            bos_level = float(recent["low"].iloc[max(0, sweep_idx - 8):sweep_idx].min())
            for idx in range(sweep_idx + 1, len(recent)):
                candle = recent.iloc[idx]
                body = candle["open"] - candle["close"]
                if candle["close"] < bos_level and body > (0.35 * atr):
                    bos_idx = idx
                    break
        if bos_idx is None:
            return snapshot, None

        impulse_low = float(recent["low"].iloc[bos_idx])
        sweep_high = float(recent["high"].iloc[sweep_idx])
        pullback_level = impulse_low + ((sweep_high - impulse_low) * 0.5)
        last_close = float(recent["close"].iloc[-1])
        last_low = float(recent["low"].iloc[-1])
        last_high = float(recent["high"].iloc[-1])
        touched_pullback = (last_low <= pullback_level <= last_high) or abs(last_close - pullback_level) <= atr * 0.2
        if not touched_pullback or last_close > bos_level:
            return snapshot, None
        entry = last_close
        stop = sweep_high + (atr * 0.25)

    signal = _build_signal(
        symbol=symbol,
        market=market,
        direction=direction,
        session=session,
        entry=entry,
        stop=stop,
        atr=atr,
        pullback_level=pullback_level,
        bos_level=bos_level,
        liquidity_level=liquidity_level,
        h1_bias=h1_bias,
        m15_trend=m15_trend,
    )
    snapshot.m5_context = {
        "setup": "ls_bos_pullback",
        "direction": direction.value,
        "liquidity_level": liquidity_level,
        "bos_level": bos_level,
        "pullback_level": pullback_level,
    }
    return snapshot, signal


def signal_to_frame(signals: list[TradeSignal]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame()
    return pd.DataFrame([asdict(signal) for signal in signals])


def displacement_score(signal: TradeSignal) -> float:
    if signal.atr <= 0:
        return 0.0
    return abs(signal.entry_price - signal.bos_level) / signal.atr


def liquidity_efficiency(signal: TradeSignal) -> float:
    risk = abs(signal.entry_price - signal.stop_loss)
    if risk <= 0:
        return 0.0
    return abs(signal.entry_price - signal.liquidity_level) / risk
