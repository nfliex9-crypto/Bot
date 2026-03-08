"""
Pullback Entry Logic.

After a BOS/CHoCH and liquidity sweep, we wait for price to retrace
into a premium/discount zone (usually an Order Block or FVG) before entering.

Entry Conditions:
  Bullish: Price pulls back into 50–79% Fibonacci retracement of the impulse move
           AND touches an identified Order Block or Fair Value Gap
  Bearish: Mirror condition
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from src.strategy.indicators import identify_order_blocks, calculate_atr


@dataclass
class FairValueGap:
    high: float
    low: float
    midpoint: float
    gap_type: str   # "bullish_fvg" | "bearish_fvg"
    bar_index: int
    filled: bool = False


@dataclass
class PullbackResult:
    valid: bool
    entry_type: Optional[str]   # "order_block" | "fvg" | "fibonacci"
    entry_zone_high: Optional[float]
    entry_zone_low: Optional[float]
    suggested_entry: Optional[float]
    fib_retracement: Optional[float]
    ob_high: Optional[float]
    ob_low: Optional[float]
    fvg: Optional[FairValueGap]


class PullbackEntryDetector:
    """
    Identifies valid pullback entry zones after structural confirmation.
    """

    FIB_ENTRY_MIN = 0.50    # 50% retracement
    FIB_ENTRY_MAX = 0.79    # 79% retracement (OTE zone)

    def __init__(self, ob_lookback: int = 3):
        self.ob_lookback = ob_lookback

    def detect(
        self,
        df: pd.DataFrame,
        direction: str,          # "bullish" | "bearish"
        impulse_start: float,    # Start price of the impulse leg
        impulse_end: float,      # End price of the impulse leg
    ) -> PullbackResult:
        """
        Check if current price is in a valid pullback entry zone.
        """
        current_price = df["close"].iloc[-1]
        fib_zone = self._calculate_fib_zone(direction, impulse_start, impulse_end)
        fib_low, fib_high = fib_zone

        in_fib_zone = fib_low <= current_price <= fib_high

        # Check for Order Block in the pullback zone
        ob_df = identify_order_blocks(df, lookback=self.ob_lookback)
        ob = self._find_ob_in_zone(ob_df, direction, fib_low, fib_high)

        # Check for Fair Value Gap
        fvg = self._find_fvg(df, direction, fib_low, fib_high)

        # Determine validity
        if in_fib_zone and ob is not None:
            mid = (ob["ob_high"] + ob["ob_low"]) / 2
            return PullbackResult(
                valid=True,
                entry_type="order_block",
                entry_zone_high=ob["ob_high"],
                entry_zone_low=ob["ob_low"],
                suggested_entry=mid,
                fib_retracement=self._calculate_retracement(direction, impulse_start, impulse_end, current_price),
                ob_high=ob["ob_high"],
                ob_low=ob["ob_low"],
                fvg=fvg,
            )

        if in_fib_zone and fvg is not None:
            return PullbackResult(
                valid=True,
                entry_type="fvg",
                entry_zone_high=fvg.high,
                entry_zone_low=fvg.low,
                suggested_entry=fvg.midpoint,
                fib_retracement=self._calculate_retracement(direction, impulse_start, impulse_end, current_price),
                ob_high=None,
                ob_low=None,
                fvg=fvg,
            )

        if in_fib_zone:
            mid_fib = (fib_low + fib_high) / 2
            return PullbackResult(
                valid=True,
                entry_type="fibonacci",
                entry_zone_high=fib_high,
                entry_zone_low=fib_low,
                suggested_entry=mid_fib,
                fib_retracement=self._calculate_retracement(direction, impulse_start, impulse_end, current_price),
                ob_high=None,
                ob_low=None,
                fvg=fvg,
            )

        return PullbackResult(
            valid=False,
            entry_type=None,
            entry_zone_high=fib_high,
            entry_zone_low=fib_low,
            suggested_entry=None,
            fib_retracement=self._calculate_retracement(direction, impulse_start, impulse_end, current_price),
            ob_high=ob["ob_high"] if ob else None,
            ob_low=ob["ob_low"] if ob else None,
            fvg=fvg,
        )

    def _calculate_fib_zone(
        self, direction: str, start: float, end: float
    ) -> Tuple[float, float]:
        """Calculate the OTE (Optimal Trade Entry) Fibonacci zone."""
        move = end - start
        if direction == "bullish":
            fib_high = end - move * self.FIB_ENTRY_MIN  # 50% retrace from top
            fib_low = end - move * self.FIB_ENTRY_MAX   # 79% retrace from top
            return fib_low, fib_high
        else:
            fib_low = end + abs(move) * self.FIB_ENTRY_MIN
            fib_high = end + abs(move) * self.FIB_ENTRY_MAX
            return fib_low, fib_high

    def _calculate_retracement(
        self, direction: str, start: float, end: float, current: float
    ) -> float:
        """Calculate how far price has retraced (0.0 = no retrace, 1.0 = full retrace)."""
        move = abs(end - start)
        if move == 0:
            return 0.0
        if direction == "bullish":
            retraced = end - current
        else:
            retraced = current - end
        return round(max(0.0, min(retraced / move, 1.0)), 4)

    def _find_ob_in_zone(
        self, ob_df: pd.DataFrame, direction: str, zone_low: float, zone_high: float
    ) -> Optional[dict]:
        """Find the most recent order block within the entry zone."""
        if direction == "bullish":
            candidates = ob_df[ob_df["bullish_ob"] == True].copy()
        else:
            candidates = ob_df[ob_df["bearish_ob"] == True].copy()

        if candidates.empty:
            return None

        # Filter OBs overlapping with the zone
        overlapping = candidates[
            (candidates["ob_high"] >= zone_low) & (candidates["ob_low"] <= zone_high)
        ]
        if overlapping.empty:
            return None

        # Return the most recent one
        return overlapping.iloc[-1][["ob_high", "ob_low"]].to_dict()

    def _find_fvg(
        self, df: pd.DataFrame, direction: str, zone_low: float, zone_high: float
    ) -> Optional[FairValueGap]:
        """
        Identify Fair Value Gaps (FVG / imbalance) within the entry zone.
        Bullish FVG: candle[i].low > candle[i-2].high  → gap between i-2 high and i low
        Bearish FVG: candle[i].high < candle[i-2].low  → gap between i high and i-2 low
        """
        for i in range(2, len(df)):
            if direction == "bullish":
                gap_high = df["low"].iloc[i]
                gap_low = df["high"].iloc[i - 2]
                if gap_high > gap_low:
                    mid = (gap_high + gap_low) / 2
                    if zone_low <= mid <= zone_high:
                        return FairValueGap(
                            high=gap_high,
                            low=gap_low,
                            midpoint=mid,
                            gap_type="bullish_fvg",
                            bar_index=i,
                        )
            else:
                gap_low = df["high"].iloc[i]
                gap_high = df["low"].iloc[i - 2]
                if gap_low < gap_high:
                    mid = (gap_high + gap_low) / 2
                    if zone_low <= mid <= zone_high:
                        return FairValueGap(
                            high=gap_high,
                            low=gap_low,
                            midpoint=mid,
                            gap_type="bearish_fvg",
                            bar_index=i,
                        )
        return None
