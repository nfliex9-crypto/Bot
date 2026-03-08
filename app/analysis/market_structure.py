from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import pandas as pd

from app.analysis.indicators import swing_highs, swing_lows


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class StructureBreak(str, Enum):
    BOS_BULLISH = "bos_bullish"
    BOS_BEARISH = "bos_bearish"
    CHOCH_BULLISH = "choch_bullish"
    CHOCH_BEARISH = "choch_bearish"


@dataclass
class SwingPoint:
    index: int
    price: float
    type: str  # "high" | "low"
    timestamp: object = None


@dataclass
class StructureResult:
    bias: Bias = Bias.NEUTRAL
    swing_points: List[SwingPoint] = field(default_factory=list)
    structure_breaks: List[dict] = field(default_factory=list)
    last_higher_high: Optional[float] = None
    last_higher_low: Optional[float] = None
    last_lower_high: Optional[float] = None
    last_lower_low: Optional[float] = None


def analyse_structure(df: pd.DataFrame, lookback: int = 5) -> StructureResult:
    """
    Identify swing points, break-of-structure (BOS), and overall market bias.
    """
    result = StructureResult()

    if len(df) < lookback * 3:
        return result

    sh = swing_highs(df, lookback)
    sl = swing_lows(df, lookback)

    highs: list[SwingPoint] = []
    lows: list[SwingPoint] = []

    for i in range(len(df)):
        ts = df["timestamp"].iloc[i] if "timestamp" in df.columns else None
        if sh.iloc[i]:
            sp = SwingPoint(index=i, price=df["high"].iloc[i], type="high", timestamp=ts)
            highs.append(sp)
            result.swing_points.append(sp)
        if sl.iloc[i]:
            sp = SwingPoint(index=i, price=df["low"].iloc[i], type="low", timestamp=ts)
            lows.append(sp)
            result.swing_points.append(sp)

    if len(highs) < 2 or len(lows) < 2:
        return result

    hh_count = 0
    ll_count = 0

    for i in range(1, len(highs)):
        if highs[i].price > highs[i - 1].price:
            hh_count += 1
            result.last_higher_high = highs[i].price
        else:
            result.last_lower_high = highs[i].price

    for i in range(1, len(lows)):
        if lows[i].price < lows[i - 1].price:
            ll_count += 1
            result.last_lower_low = lows[i].price
        else:
            result.last_higher_low = lows[i].price

    # Detect BOS events on the last few swing points
    _detect_breaks(highs, lows, df, result)

    recent_highs = highs[-3:]
    recent_lows = lows[-3:]
    rh_up = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i].price > recent_highs[i - 1].price)
    rl_up = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i].price > recent_lows[i - 1].price)
    rh_dn = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i].price < recent_highs[i - 1].price)
    rl_dn = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i].price < recent_lows[i - 1].price)

    if rh_up >= 1 and rl_up >= 1:
        result.bias = Bias.BULLISH
    elif rh_dn >= 1 and rl_dn >= 1:
        result.bias = Bias.BEARISH
    else:
        result.bias = Bias.NEUTRAL

    return result


def _detect_breaks(
    highs: list[SwingPoint],
    lows: list[SwingPoint],
    df: pd.DataFrame,
    result: StructureResult,
) -> None:
    """Detect break-of-structure / change-of-character from swing points."""
    for i in range(1, len(highs)):
        if highs[i].price > highs[i - 1].price:
            result.structure_breaks.append(
                {
                    "type": StructureBreak.BOS_BULLISH.value,
                    "price": highs[i - 1].price,
                    "break_price": highs[i].price,
                    "index": highs[i].index,
                }
            )
        elif highs[i].price < highs[i - 1].price and i >= 2 and highs[i - 1].price > highs[i - 2].price:
            result.structure_breaks.append(
                {
                    "type": StructureBreak.CHOCH_BEARISH.value,
                    "price": highs[i - 1].price,
                    "break_price": highs[i].price,
                    "index": highs[i].index,
                }
            )

    for i in range(1, len(lows)):
        if lows[i].price < lows[i - 1].price:
            result.structure_breaks.append(
                {
                    "type": StructureBreak.BOS_BEARISH.value,
                    "price": lows[i - 1].price,
                    "break_price": lows[i].price,
                    "index": lows[i].index,
                }
            )
        elif lows[i].price > lows[i - 1].price and i >= 2 and lows[i - 1].price < lows[i - 2].price:
            result.structure_breaks.append(
                {
                    "type": StructureBreak.CHOCH_BULLISH.value,
                    "price": lows[i - 1].price,
                    "break_price": lows[i].price,
                    "index": lows[i].index,
                }
            )
