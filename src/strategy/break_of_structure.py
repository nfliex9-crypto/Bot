"""
Break of Structure (BOS) and Change of Character (CHoCH) Detection.

BOS: Market continues in the prevailing direction by breaking the last
     significant swing high/low in the direction of trend.

CHoCH: A structural shift — price breaks the last opposing swing point,
       signalling a potential trend reversal.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from src.strategy.indicators import find_swing_highs, find_swing_lows


@dataclass
class StructurePoint:
    index: int
    price: float
    point_type: str   # "higher_high", "lower_low", "higher_low", "lower_high"
    bar_time: object  # datetime


@dataclass
class BOSResult:
    detected: bool
    bos_type: Optional[str]     # "bullish_bos", "bearish_bos", "bullish_choch", "bearish_choch"
    broken_level: Optional[float]
    break_bar: Optional[int]
    trend: Optional[str]         # "bullish" | "bearish" | "ranging"
    structure_points: List[StructurePoint] = field(default_factory=list)
    strength: float = 0.0


class BreakOfStructureDetector:
    """
    Detects Break of Structure and Change of Character patterns.
    """

    def __init__(self, lookback: int = 5, confirmation_bars: int = 1):
        self.lookback = lookback
        self.confirmation_bars = confirmation_bars

    def detect(self, df: pd.DataFrame) -> BOSResult:
        """
        Analyse df for the most recent BOS/CHoCH.
        Returns BOSResult with detection details.
        """
        if len(df) < self.lookback * 3:
            return BOSResult(detected=False, bos_type=None, broken_level=None,
                             break_bar=None, trend=None)

        structure_points = self._build_structure(df)
        trend = self._determine_trend(structure_points)
        bos = self._detect_break(df, structure_points, trend)
        bos.trend = trend
        return bos

    def _build_structure(self, df: pd.DataFrame) -> List[StructurePoint]:
        """Build a sequence of swing highs and lows ordered chronologically."""
        swing_h_mask = find_swing_highs(df, lookback=self.lookback)
        swing_l_mask = find_swing_lows(df, lookback=self.lookback)

        points: List[StructurePoint] = []

        for i, idx in enumerate(df.index):
            if swing_h_mask.iloc[i]:
                points.append(StructurePoint(
                    index=i,
                    price=df.loc[idx, "high"],
                    point_type="swing_high",
                    bar_time=df.loc[idx, "open_time"] if "open_time" in df.columns else idx,
                ))
            if swing_l_mask.iloc[i]:
                points.append(StructurePoint(
                    index=i,
                    price=df.loc[idx, "low"],
                    point_type="swing_low",
                    bar_time=df.loc[idx, "open_time"] if "open_time" in df.columns else idx,
                ))

        points.sort(key=lambda p: p.index)

        # Classify as HH/HL/LH/LL
        return self._classify_structure(points)

    def _classify_structure(self, points: List[StructurePoint]) -> List[StructurePoint]:
        """Label each swing point as HH/HL/LH/LL relative to the previous same-type point."""
        last_high: Optional[float] = None
        last_low: Optional[float] = None

        for point in points:
            if point.point_type == "swing_high":
                if last_high is None:
                    point.point_type = "swing_high"
                elif point.price > last_high:
                    point.point_type = "higher_high"
                else:
                    point.point_type = "lower_high"
                last_high = point.price

            elif point.point_type == "swing_low":
                if last_low is None:
                    point.point_type = "swing_low"
                elif point.price > last_low:
                    point.point_type = "higher_low"
                else:
                    point.point_type = "lower_low"
                last_low = point.price

        return points

    def _determine_trend(self, points: List[StructurePoint]) -> str:
        """Determine current trend from recent structure."""
        if len(points) < 4:
            return "ranging"

        recent = points[-6:]
        hh_count = sum(1 for p in recent if p.point_type == "higher_high")
        hl_count = sum(1 for p in recent if p.point_type == "higher_low")
        ll_count = sum(1 for p in recent if p.point_type == "lower_low")
        lh_count = sum(1 for p in recent if p.point_type == "lower_high")

        bull_score = hh_count + hl_count
        bear_score = ll_count + lh_count

        if bull_score > bear_score + 1:
            return "bullish"
        elif bear_score > bull_score + 1:
            return "bearish"
        return "ranging"

    def _detect_break(
        self, df: pd.DataFrame, structure_points: List[StructurePoint], trend: str
    ) -> BOSResult:
        """
        Scan recent bars for BOS/CHoCH.

        BOS Bullish: price closes above last swing high → trend continuation
        BOS Bearish: price closes below last swing low → trend continuation
        CHoCH Bullish: price in downtrend closes above last lower_high → reversal signal
        CHoCH Bearish: price in uptrend closes below last higher_low → reversal signal
        """
        if len(structure_points) < 2:
            return BOSResult(detected=False, bos_type=None, broken_level=None,
                             break_bar=None, trend=trend, structure_points=structure_points)

        recent_close = df["close"].iloc[-1]
        check_window = min(5, len(df))
        recent_df = df.iloc[-check_window:]

        # Get last significant levels
        swing_highs = [p for p in structure_points if "high" in p.point_type]
        swing_lows = [p for p in structure_points if "low" in p.point_type]

        if not swing_highs or not swing_lows:
            return BOSResult(detected=False, bos_type=None, broken_level=None,
                             break_bar=None, trend=trend, structure_points=structure_points)

        last_swing_high = swing_highs[-1]
        last_swing_low = swing_lows[-1]

        # Check for bullish BOS (close above last swing high)
        if trend == "bullish" and recent_close > last_swing_high.price:
            # Confirm it's a clean close, not just a wick
            if df["close"].iloc[-1] > last_swing_high.price:
                strength = min((recent_close - last_swing_high.price) / last_swing_high.price * 100, 1.0)
                return BOSResult(
                    detected=True,
                    bos_type="bullish_bos",
                    broken_level=last_swing_high.price,
                    break_bar=len(df) - 1,
                    trend=trend,
                    structure_points=structure_points,
                    strength=round(strength, 4),
                )

        # Check for bearish BOS (close below last swing low)
        if trend == "bearish" and recent_close < last_swing_low.price:
            if df["close"].iloc[-1] < last_swing_low.price:
                strength = min((last_swing_low.price - recent_close) / last_swing_low.price * 100, 1.0)
                return BOSResult(
                    detected=True,
                    bos_type="bearish_bos",
                    broken_level=last_swing_low.price,
                    break_bar=len(df) - 1,
                    trend=trend,
                    structure_points=structure_points,
                    strength=round(strength, 4),
                )

        # Check for bullish CHoCH (downtrend: close above last lower_high)
        lower_highs = [p for p in structure_points if p.point_type == "lower_high"]
        higher_lows = [p for p in structure_points if p.point_type == "higher_low"]

        if trend == "bearish" and lower_highs:
            last_lh = lower_highs[-1]
            if recent_close > last_lh.price:
                strength = min((recent_close - last_lh.price) / last_lh.price * 100, 1.0)
                return BOSResult(
                    detected=True,
                    bos_type="bullish_choch",
                    broken_level=last_lh.price,
                    break_bar=len(df) - 1,
                    trend=trend,
                    structure_points=structure_points,
                    strength=round(strength, 4),
                )

        # Check for bearish CHoCH (uptrend: close below last higher_low)
        if trend == "bullish" and higher_lows:
            last_hl = higher_lows[-1]
            if recent_close < last_hl.price:
                strength = min((last_hl.price - recent_close) / last_hl.price * 100, 1.0)
                return BOSResult(
                    detected=True,
                    bos_type="bearish_choch",
                    broken_level=last_hl.price,
                    break_bar=len(df) - 1,
                    trend=trend,
                    structure_points=structure_points,
                    strength=round(strength, 4),
                )

        return BOSResult(
            detected=False,
            bos_type=None,
            broken_level=None,
            break_bar=None,
            trend=trend,
            structure_points=structure_points,
        )

    def get_last_structure_levels(self, df: pd.DataFrame) -> Tuple[Optional[float], Optional[float]]:
        """Return the most recent swing high and swing low prices."""
        structure_points = self._build_structure(df)
        highs = [p for p in structure_points if "high" in p.point_type]
        lows = [p for p in structure_points if "low" in p.point_type]
        last_high = highs[-1].price if highs else None
        last_low = lows[-1].price if lows else None
        return last_high, last_low
