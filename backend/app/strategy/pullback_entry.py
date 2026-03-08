"""
Pullback Entry Model

After a Liquidity Sweep + Break of Structure, this module identifies the optimal
entry on a pullback into the BOS zone. Entries are refined using:
- Order Block detection (last bearish/bullish candle before impulsive move)
- Fair Value Gap (FVG) detection
- Fibonacci retracement (0.5 / 0.618)
- RSI confirmation (oversold for longs, overbought for shorts)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple

from app.strategy.break_of_structure import BOSEvent


@dataclass
class EntrySignal:
    direction: str           # "LONG" or "SHORT"
    entry_price: float
    entry_zone_low: float
    entry_zone_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr: float
    rsi_value: float
    order_block_level: Optional[float]
    fvg_detected: bool
    fib_level: str           # "0.5" or "0.618"
    setup_quality: float     # 0.0 - 1.0


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def detect_order_block(
    df: pd.DataFrame,
    direction: str,
    lookback: int = 20,
) -> Optional[float]:
    """
    Find the last opposite-direction candle before the impulsive BOS move.
    For LONG: find the last bearish candle before bullish impulse.
    For SHORT: find the last bullish candle before bearish impulse.
    """
    ref = df.iloc[-lookback:-3]
    if direction == "LONG":
        # Last bearish candle (potential demand zone / order block)
        bearish = ref[ref["close"] < ref["open"]]
        if not bearish.empty:
            last = bearish.iloc[-1]
            return (last["open"] + last["close"]) / 2
    else:
        # Last bullish candle (potential supply zone / order block)
        bullish = ref[ref["close"] > ref["open"]]
        if not bullish.empty:
            last = bullish.iloc[-1]
            return (last["open"] + last["close"]) / 2
    return None


def detect_fair_value_gap(df: pd.DataFrame, direction: str) -> Optional[Tuple[float, float]]:
    """
    Detect a Fair Value Gap (3-candle pattern where candle 1 and candle 3
    do not overlap, leaving a 'gap' in price that acts as a magnet).
    Returns (fvg_low, fvg_high) or None.
    """
    if len(df) < 4:
        return None

    for i in range(len(df) - 4, len(df) - 1):
        c1 = df.iloc[i]
        c3 = df.iloc[i + 2]

        if direction == "LONG":
            # Bullish FVG: c3 low > c1 high
            if c3["low"] > c1["high"]:
                return c1["high"], c3["low"]
        else:
            # Bearish FVG: c3 high < c1 low
            if c3["high"] < c1["low"]:
                return c3["high"], c1["low"]

    return None


def calculate_fibonacci_levels(
    swing_high: float,
    swing_low: float,
    direction: str,
) -> dict:
    diff = swing_high - swing_low
    if direction == "LONG":
        return {
            "0.236": swing_high - diff * 0.236,
            "0.382": swing_high - diff * 0.382,
            "0.5": swing_high - diff * 0.5,
            "0.618": swing_high - diff * 0.618,
            "0.786": swing_high - diff * 0.786,
        }
    else:
        return {
            "0.236": swing_low + diff * 0.236,
            "0.382": swing_low + diff * 0.382,
            "0.5": swing_low + diff * 0.5,
            "0.618": swing_low + diff * 0.618,
            "0.786": swing_low + diff * 0.786,
        }


def build_entry_signal(
    df: pd.DataFrame,
    bos: BOSEvent,
    direction: str,
    atr: float,
    tp1_ratio: float = 1.5,
    tp2_ratio: float = 2.5,
    tp3_ratio: float = 4.0,
) -> Optional[EntrySignal]:
    """
    Build a full entry signal after BOS confirmation.

    Parameters
    ----------
    df : Full OHLCV DataFrame
    bos : Confirmed BOS event
    direction : "LONG" or "SHORT"
    atr : Current ATR value
    """
    if len(df) < 30:
        return None

    rsi = calculate_rsi(df["close"])
    rsi_now = rsi.iloc[-1]

    # RSI filter: avoid buying into overbought, avoid selling into oversold
    if direction == "LONG" and rsi_now > 70:
        return None
    if direction == "SHORT" and rsi_now < 30:
        return None

    # Determine swing range for Fibonacci
    lookback_fib = 20
    ref = df.iloc[-lookback_fib:]
    swing_high = ref["high"].max()
    swing_low = ref["low"].min()

    fib_levels = calculate_fibonacci_levels(swing_high, swing_low, direction)
    fib_label = "0.618"

    # Preferred entry: 0.618 retrace; fallback 0.5
    current_price = df["close"].iloc[-1]
    fib_618 = fib_levels["0.618"]
    fib_50 = fib_levels["0.5"]

    if direction == "LONG":
        # Entry zone: between 50% and 61.8% retrace (demand)
        entry_zone_low = min(fib_618, fib_50) - atr * 0.1
        entry_zone_high = max(fib_618, fib_50) + atr * 0.1
        entry_price = (fib_618 + fib_50) / 2

        # Stop: below the sweep low with ATR buffer
        sweep_low = df["low"].iloc[-10:].min()
        stop_loss = sweep_low - atr * 1.0

        sl_distance = entry_price - stop_loss
        tp1 = entry_price + sl_distance * tp1_ratio
        tp2 = entry_price + sl_distance * tp2_ratio
        tp3 = entry_price + sl_distance * tp3_ratio
    else:
        # Entry zone: between 50% and 61.8% retrace (supply)
        entry_zone_low = min(fib_618, fib_50) - atr * 0.1
        entry_zone_high = max(fib_618, fib_50) + atr * 0.1
        entry_price = (fib_618 + fib_50) / 2

        # Stop: above the sweep high with ATR buffer
        sweep_high = df["high"].iloc[-10:].max()
        stop_loss = sweep_high + atr * 1.0

        sl_distance = stop_loss - entry_price
        tp1 = entry_price - sl_distance * tp1_ratio
        tp2 = entry_price - sl_distance * tp2_ratio
        tp3 = entry_price - sl_distance * tp3_ratio

    # Detect optional confluence
    order_block = detect_order_block(df, direction)
    fvg = detect_fair_value_gap(df, direction)

    # Quality scoring
    quality = 0.5
    if bos.impulse_size >= 1.5:
        quality += 0.1
    if fvg is not None:
        quality += 0.1
    if order_block is not None:
        quality += 0.1
    if (direction == "LONG" and rsi_now < 45) or (direction == "SHORT" and rsi_now > 55):
        quality += 0.1
    if bos.structure_strength >= 5:
        quality += 0.1

    quality = min(quality, 1.0)

    return EntrySignal(
        direction=direction,
        entry_price=entry_price,
        entry_zone_low=entry_zone_low,
        entry_zone_high=entry_zone_high,
        stop_loss=stop_loss,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        atr=atr,
        rsi_value=float(rsi_now),
        order_block_level=order_block,
        fvg_detected=fvg is not None,
        fib_level=fib_label,
        setup_quality=quality,
    )
