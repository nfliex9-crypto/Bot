from dataclasses import dataclass

import pandas as pd

from app.strategy.market_structure import (
    StrategySignal,
    detect_break_of_structure,
    detect_liquidity_sweep,
    detect_pullback_entry,
)


@dataclass(slots=True)
class TimeframeContext:
    h1_bias: str
    m15_structure: str
    m5_triggered: bool


def h1_bias(df_h1: pd.DataFrame) -> str:
    if len(df_h1) < 50:
        return "neutral"
    sma_fast = df_h1["close"].rolling(20).mean().iloc[-1]
    sma_slow = df_h1["close"].rolling(50).mean().iloc[-1]
    if sma_fast > sma_slow:
        return "bullish"
    if sma_fast < sma_slow:
        return "bearish"
    return "neutral"


def m15_trend_structure(df_m15: pd.DataFrame, bias: str) -> str:
    if bias not in {"bullish", "bearish"}:
        return "invalid"
    has_bos = detect_break_of_structure(df_m15, direction=bias)
    return "aligned" if has_bos else "not_aligned"


def analyze_signal(
    df_h1: pd.DataFrame,
    df_m15: pd.DataFrame,
    df_m5: pd.DataFrame,
    atr_period: int,
    atr_multiplier: float,
    stop_type: str,
) -> tuple[TimeframeContext, StrategySignal | None]:
    bias = h1_bias(df_h1)
    structure = m15_trend_structure(df_m15, bias)
    sweep = detect_liquidity_sweep(df_m5)
    trigger = sweep is not None and sweep == bias and structure == "aligned"
    context = TimeframeContext(h1_bias=bias, m15_structure=structure, m5_triggered=trigger)
    if not trigger:
        return context, None

    signal = detect_pullback_entry(
        df=df_m5,
        direction=sweep,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
        stop_type=stop_type,  # type: ignore[arg-type]
    )
    return context, signal
