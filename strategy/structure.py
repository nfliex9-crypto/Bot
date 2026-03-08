"""
Market structure analysis: swing points, break of structure (BOS),
change of character (CHoCH), and trend identification.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.models import (
    Direction, MarketBias, StructureBreak, StructureType, SwingPoint,
)

logger = get_logger("strategy.structure")


class StructureAnalyzer:
    def __init__(self, lookback: int = 30):
        self.lookback = lookback

    def find_swing_points(self, df: pd.DataFrame, left: int = 5, right: int = 5) -> List[SwingPoint]:
        """Identify swing highs and swing lows using left/right bar comparison."""
        swings = []
        highs = df["high"].values
        lows = df["low"].values
        times = df["timestamp"].values

        for i in range(left, len(df) - right):
            is_swing_high = all(highs[i] > highs[i - j] for j in range(1, left + 1)) and \
                            all(highs[i] > highs[i + j] for j in range(1, right + 1))
            if is_swing_high:
                strength = sum(1 for j in range(1, left + 1) if highs[i] - highs[i - j] > 0)
                swings.append(SwingPoint(
                    timestamp=pd.Timestamp(times[i]).to_pydatetime(),
                    price=float(highs[i]), is_high=True, strength=strength,
                ))

            is_swing_low = all(lows[i] < lows[i - j] for j in range(1, left + 1)) and \
                           all(lows[i] < lows[i + j] for j in range(1, right + 1))
            if is_swing_low:
                strength = sum(1 for j in range(1, left + 1) if lows[i - j] - lows[i] > 0)
                swings.append(SwingPoint(
                    timestamp=pd.Timestamp(times[i]).to_pydatetime(),
                    price=float(lows[i]), is_high=False, strength=strength,
                ))

        return sorted(swings, key=lambda s: s.timestamp)

    def detect_structure_breaks(self, swings: List[SwingPoint]) -> List[StructureBreak]:
        """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
        breaks = []
        if len(swings) < 4:
            return breaks

        swing_highs = [s for s in swings if s.is_high]
        swing_lows = [s for s in swings if not s.is_high]

        for i in range(1, len(swing_highs)):
            prev, curr = swing_highs[i - 1], swing_highs[i]
            if curr.price > prev.price:
                breaks.append(StructureBreak(
                    break_type=StructureType.BREAK_OF_STRUCTURE,
                    price=curr.price, timestamp=curr.timestamp,
                    direction=Direction.LONG, confirmed=True,
                ))

        for i in range(1, len(swing_lows)):
            prev, curr = swing_lows[i - 1], swing_lows[i]
            if curr.price < prev.price:
                breaks.append(StructureBreak(
                    break_type=StructureType.BREAK_OF_STRUCTURE,
                    price=curr.price, timestamp=curr.timestamp,
                    direction=Direction.SHORT, confirmed=True,
                ))

        self._detect_choch(swing_highs, swing_lows, breaks)
        return sorted(breaks, key=lambda b: b.timestamp)

    def _detect_choch(
        self, highs: List[SwingPoint], lows: List[SwingPoint], breaks: List[StructureBreak]
    ):
        """Detect Change of Character — trend reversal signals."""
        if len(highs) < 2 or len(lows) < 2:
            return

        if highs[-1].price < highs[-2].price and lows[-1].price < lows[-2].price:
            if len(highs) >= 3 and highs[-3].price < highs[-2].price:
                breaks.append(StructureBreak(
                    break_type=StructureType.CHANGE_OF_CHARACTER,
                    price=lows[-1].price, timestamp=lows[-1].timestamp,
                    direction=Direction.SHORT, confirmed=True,
                ))

        if lows[-1].price > lows[-2].price and highs[-1].price > highs[-2].price:
            if len(lows) >= 3 and lows[-3].price > lows[-2].price:
                breaks.append(StructureBreak(
                    break_type=StructureType.CHANGE_OF_CHARACTER,
                    price=highs[-1].price, timestamp=highs[-1].timestamp,
                    direction=Direction.LONG, confirmed=True,
                ))

    def determine_bias(self, swings: List[SwingPoint]) -> MarketBias:
        """Determine market bias from recent swing structure."""
        if len(swings) < 4:
            return MarketBias.NEUTRAL

        recent = swings[-8:] if len(swings) >= 8 else swings
        highs = [s for s in recent if s.is_high]
        lows = [s for s in recent if not s.is_high]

        if len(highs) < 2 or len(lows) < 2:
            return MarketBias.NEUTRAL

        hh = highs[-1].price > highs[-2].price
        hl = lows[-1].price > lows[-2].price
        ll = lows[-1].price < lows[-2].price
        lh = highs[-1].price < highs[-2].price

        if hh and hl:
            return MarketBias.BULLISH
        if ll and lh:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    def get_trend_direction(self, df: pd.DataFrame) -> Tuple[MarketBias, List[SwingPoint], List[StructureBreak]]:
        """Full structure analysis returning bias, swings, and breaks."""
        swings = self.find_swing_points(df)
        breaks = self.detect_structure_breaks(swings)
        bias = self.determine_bias(swings)
        return bias, swings, breaks
