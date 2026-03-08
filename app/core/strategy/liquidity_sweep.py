"""
Liquidity Sweep Detection.

A liquidity sweep occurs when price "hunts" liquidity resting above swing highs
(buy-side liquidity) or below swing lows (sell-side liquidity), briefly wicking
through them before reversing. This is the manipulation phase of Smart Money.

Detection logic:
1. Find equal highs/lows or swing highs/lows (liquidity pools)
2. Detect when price wicks through the level
3. Confirm the wick closes BACK past the level (rejection)
4. The closer to the current bar, the more relevant
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List
from app.utils.indicators import find_swing_highs, find_swing_lows, calculate_atr
from app.utils.logger import get_logger

logger = get_logger("liquidity_sweep")


@dataclass
class SweepResult:
    detected: bool = False
    direction: Optional[str] = None          # "bullish" (swept lows) | "bearish" (swept highs)
    sweep_level: Optional[float] = None      # The liquidity level that was swept
    sweep_type: Optional[str] = None         # "equal_highs" | "swing_high" | "equal_lows" | "swing_low"
    sweep_bar_index: Optional[int] = None    # Index of sweep bar
    sweep_low: Optional[float] = None        # Extreme of the sweep wick
    sweep_high: Optional[float] = None
    rejection_strength: float = 0.0          # How strong the rejection was (0-1)
    bars_ago: int = 0                         # How many bars ago was the sweep
    atr: float = 0.0


class LiquiditySweepDetector:
    """
    Detects liquidity sweeps on a price series.

    A valid sweep requires:
    - A clear liquidity pool (swing high/low or equal highs/lows)
    - A wick that pierces through the level
    - A candle close that returns past the swept level (rejection)
    - The rejection is within a lookback window
    """

    def __init__(
        self,
        lookback: int = 20,
        swing_lookback: int = 5,
        equal_tolerance: float = 0.0015,  # 0.15% for equal H/L
        min_sweep_atr_ratio: float = 0.3,  # Minimum wick size vs ATR
        max_bars_since_sweep: int = 5,
    ):
        self.lookback = lookback
        self.swing_lookback = swing_lookback
        self.equal_tolerance = equal_tolerance
        self.min_sweep_atr_ratio = min_sweep_atr_ratio
        self.max_bars_since_sweep = max_bars_since_sweep

    def detect(self, df: pd.DataFrame) -> SweepResult:
        """
        Detect the most recent liquidity sweep.

        Args:
            df: OHLCV DataFrame with at least `lookback + swing_lookback * 2` bars

        Returns:
            SweepResult with detection details
        """
        if len(df) < self.lookback + self.swing_lookback * 2 + 5:
            return SweepResult(detected=False)

        atr_series = calculate_atr(df, 14)
        current_atr = atr_series.iloc[-1]

        # Search recent bars for a sweep (most recent first)
        for bars_ago in range(1, self.max_bars_since_sweep + 1):
            sweep_idx = len(df) - 1 - bars_ago
            if sweep_idx < self.lookback:
                continue

            sweep_candle = df.iloc[sweep_idx]
            result = self._check_sweep_at_bar(
                df, sweep_idx, current_atr, bars_ago
            )
            if result.detected:
                return result

        return SweepResult(detected=False)

    def _check_sweep_at_bar(
        self,
        df: pd.DataFrame,
        idx: int,
        atr: float,
        bars_ago: int,
    ) -> SweepResult:
        """Check if a sweep occurred at a specific bar index."""
        candle = df.iloc[idx]
        lookback_slice = df.iloc[max(0, idx - self.lookback): idx]

        if len(lookback_slice) < self.swing_lookback * 2:
            return SweepResult(detected=False)

        # --- Check for BEARISH sweep (swept highs, then closed below) ---
        highs = self._find_liquidity_levels(lookback_slice, "high")
        for level, level_type in highs:
            if self._is_high_swept(candle, level, atr):
                rejection_strength = self._calc_rejection_strength(candle, level, "high", atr)
                logger.debug(
                    f"Bearish sweep detected at idx={idx}, level={level:.5f}, "
                    f"rejection={rejection_strength:.2f}"
                )
                return SweepResult(
                    detected=True,
                    direction="bearish",
                    sweep_level=level,
                    sweep_type=level_type,
                    sweep_bar_index=idx,
                    sweep_high=candle["high"],
                    rejection_strength=rejection_strength,
                    bars_ago=bars_ago,
                    atr=atr,
                )

        # --- Check for BULLISH sweep (swept lows, then closed above) ---
        lows = self._find_liquidity_levels(lookback_slice, "low")
        for level, level_type in lows:
            if self._is_low_swept(candle, level, atr):
                rejection_strength = self._calc_rejection_strength(candle, level, "low", atr)
                logger.debug(
                    f"Bullish sweep detected at idx={idx}, level={level:.5f}, "
                    f"rejection={rejection_strength:.2f}"
                )
                return SweepResult(
                    detected=True,
                    direction="bullish",
                    sweep_level=level,
                    sweep_type=level_type,
                    sweep_bar_index=idx,
                    sweep_low=candle["low"],
                    rejection_strength=rejection_strength,
                    bars_ago=bars_ago,
                    atr=atr,
                )

        return SweepResult(detected=False)

    def _find_liquidity_levels(
        self,
        df: pd.DataFrame,
        side: str,
    ) -> List[tuple]:
        """
        Find liquidity pools (equal levels or swing extremes).
        Returns list of (price_level, type) tuples sorted by relevance.
        """
        levels = []

        if side == "high":
            # Find equal highs
            highs = df["high"].values
            for i in range(len(highs)):
                for j in range(i + 1, len(highs)):
                    diff = abs(highs[i] - highs[j]) / ((highs[i] + highs[j]) / 2)
                    if diff <= self.equal_tolerance:
                        levels.append((max(highs[i], highs[j]), "equal_highs"))
                        break

            # Swing highs
            swing_mask = find_swing_highs(df, self.swing_lookback)
            if swing_mask.any():
                swing_highs = df.loc[swing_mask, "high"].values
                for h in swing_highs[-3:]:  # Most recent 3
                    levels.append((h, "swing_high"))

        elif side == "low":
            # Find equal lows
            lows = df["low"].values
            for i in range(len(lows)):
                for j in range(i + 1, len(lows)):
                    diff = abs(lows[i] - lows[j]) / ((lows[i] + lows[j]) / 2)
                    if diff <= self.equal_tolerance:
                        levels.append((min(lows[i], lows[j]), "equal_lows"))
                        break

            # Swing lows
            swing_mask = find_swing_lows(df, self.swing_lookback)
            if swing_mask.any():
                swing_lows = df.loc[swing_mask, "low"].values
                for l in swing_lows[-3:]:
                    levels.append((l, "swing_low"))

        # Remove duplicates and sort
        seen = set()
        unique_levels = []
        for level, ltype in levels:
            rounded = round(level, 5)
            if rounded not in seen:
                seen.add(rounded)
                unique_levels.append((level, ltype))

        return unique_levels

    def _is_high_swept(self, candle: pd.Series, level: float, atr: float) -> bool:
        """Check if this candle swept above the level and closed below it."""
        min_sweep = level + atr * self.min_sweep_atr_ratio * 0.3
        swept_above = candle["high"] > level
        closed_below = candle["close"] < level
        wick_size = candle["high"] - max(candle["open"], candle["close"])
        min_wick = atr * self.min_sweep_atr_ratio
        return swept_above and closed_below and wick_size >= min_wick

    def _is_low_swept(self, candle: pd.Series, level: float, atr: float) -> bool:
        """Check if this candle swept below the level and closed above it."""
        swept_below = candle["low"] < level
        closed_above = candle["close"] > level
        wick_size = min(candle["open"], candle["close"]) - candle["low"]
        min_wick = atr * self.min_sweep_atr_ratio
        return swept_below and closed_above and wick_size >= min_wick

    def _calc_rejection_strength(
        self,
        candle: pd.Series,
        level: float,
        side: str,
        atr: float,
    ) -> float:
        """
        Rejection strength from 0.0 to 1.0.
        Higher = stronger rejection away from the swept level.
        """
        candle_range = candle["high"] - candle["low"]
        if candle_range == 0 or atr == 0:
            return 0.0

        if side == "high":
            wick = candle["high"] - max(candle["open"], candle["close"])
            body_away = level - candle["close"]
        else:
            wick = min(candle["open"], candle["close"]) - candle["low"]
            body_away = candle["close"] - level

        wick_ratio = min(wick / (atr + 1e-10), 1.0)
        body_ratio = min(body_away / (atr + 1e-10), 1.0)
        return round((wick_ratio * 0.6 + body_ratio * 0.4), 3)
