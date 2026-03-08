"""
Liquidity Sweep Detection.

A liquidity sweep occurs when price transiently breaks through a key level
(equal highs/lows, prior swing, session extremes) to trigger stop orders,
then reverses sharply — indicating institutional accumulation/distribution.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from src.strategy.indicators import find_swing_highs, find_swing_lows


@dataclass
class LiquidityLevel:
    price: float
    level_type: str          # "equal_highs", "equal_lows", "swing_high", "swing_low", "session_high", "session_low"
    strength: float          # 0–1 score
    touch_count: int
    bar_index: int
    swept: bool = False
    sweep_bar: Optional[int] = None


@dataclass
class SweepResult:
    detected: bool
    direction: Optional[str]   # "bullish" (swept lows → expect rally) | "bearish" (swept highs → expect drop)
    swept_level: Optional[float]
    sweep_low: Optional[float]  # Wick low during sweep
    sweep_high: Optional[float] # Wick high during sweep
    reversal_bar: Optional[int]
    strength: float
    levels: List[LiquidityLevel] = field(default_factory=list)


class LiquiditySweepDetector:
    """
    Identifies liquidity sweeps on a given OHLCV DataFrame.
    """

    EQUAL_THRESHOLD = 0.0005  # 0.05% price tolerance for "equal" levels

    def __init__(self, lookback: int = 10, min_wick_ratio: float = 0.6):
        self.lookback = lookback
        self.min_wick_ratio = min_wick_ratio  # Wick must be ≥60% of bar range for sweep

    def detect(self, df: pd.DataFrame) -> SweepResult:
        """
        Analyse the most recent bars for a liquidity sweep.
        Expects df with columns: open, high, low, close, volume
        """
        if len(df) < self.lookback * 2:
            return SweepResult(detected=False, direction=None, swept_level=None,
                               sweep_low=None, sweep_high=None, reversal_bar=None, strength=0.0)

        levels = self._identify_liquidity_levels(df)
        sweep = self._detect_sweep(df, levels)
        return sweep

    def _identify_liquidity_levels(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        levels: List[LiquidityLevel] = []

        # 1. Equal highs and lows (clustered price levels)
        levels.extend(self._find_equal_levels(df))

        # 2. Swing highs and lows
        swing_h = find_swing_highs(df, lookback=self.lookback // 2)
        swing_l = find_swing_lows(df, lookback=self.lookback // 2)

        for idx in df.index[swing_h]:
            i = df.index.get_loc(idx)
            levels.append(LiquidityLevel(
                price=df.loc[idx, "high"],
                level_type="swing_high",
                strength=0.7,
                touch_count=1,
                bar_index=i,
            ))

        for idx in df.index[swing_l]:
            i = df.index.get_loc(idx)
            levels.append(LiquidityLevel(
                price=df.loc[idx, "low"],
                level_type="swing_low",
                strength=0.7,
                touch_count=1,
                bar_index=i,
            ))

        return levels

    def _find_equal_levels(self, df: pd.DataFrame) -> List[LiquidityLevel]:
        """Find clusters of equal highs and equal lows."""
        levels: List[LiquidityLevel] = []
        highs = df["high"].values
        lows = df["low"].values

        # Equal highs
        for i in range(len(highs)):
            cluster = []
            for j in range(i + 1, min(i + self.lookback, len(highs))):
                if abs(highs[i] - highs[j]) / highs[i] < self.EQUAL_THRESHOLD:
                    cluster.append(j)
            if len(cluster) >= 1:
                avg_price = np.mean([highs[i]] + [highs[k] for k in cluster])
                levels.append(LiquidityLevel(
                    price=avg_price,
                    level_type="equal_highs",
                    strength=min(0.5 + len(cluster) * 0.1, 0.95),
                    touch_count=len(cluster) + 1,
                    bar_index=i,
                ))

        # Equal lows
        for i in range(len(lows)):
            cluster = []
            for j in range(i + 1, min(i + self.lookback, len(lows))):
                if abs(lows[i] - lows[j]) / lows[i] < self.EQUAL_THRESHOLD:
                    cluster.append(j)
            if len(cluster) >= 1:
                avg_price = np.mean([lows[i]] + [lows[k] for k in cluster])
                levels.append(LiquidityLevel(
                    price=avg_price,
                    level_type="equal_lows",
                    strength=min(0.5 + len(cluster) * 0.1, 0.95),
                    touch_count=len(cluster) + 1,
                    bar_index=i,
                ))

        return levels

    def _detect_sweep(self, df: pd.DataFrame, levels: List[LiquidityLevel]) -> SweepResult:
        """
        Check the last N bars for price sweeping through a level and reversing.
        A bullish sweep: price wicks below a liquidity low then closes back above.
        A bearish sweep: price wicks above a liquidity high then closes back below.
        """
        check_bars = min(5, len(df))
        recent = df.iloc[-check_bars:]

        best_sweep: Optional[SweepResult] = None
        best_strength = 0.0

        for i, row in enumerate(recent.itertuples()):
            bar_range = row.high - row.low
            if bar_range == 0:
                continue

            for level in levels:
                # Must be a historical level (not current bar)
                if level.bar_index >= len(df) - check_bars + i:
                    continue

                # ─── Bullish sweep: wick below equal lows / swing low ─────────
                if level.level_type in ("equal_lows", "swing_low", "session_low"):
                    if row.low < level.price and row.close > level.price:
                        wick_size = level.price - row.low
                        wick_ratio = wick_size / bar_range
                        if wick_ratio >= self.min_wick_ratio:
                            strength = level.strength * wick_ratio
                            if strength > best_strength:
                                best_strength = strength
                                best_sweep = SweepResult(
                                    detected=True,
                                    direction="bullish",
                                    swept_level=level.price,
                                    sweep_low=row.low,
                                    sweep_high=row.high,
                                    reversal_bar=len(df) - check_bars + i,
                                    strength=round(strength, 4),
                                    levels=levels,
                                )

                # ─── Bearish sweep: wick above equal highs / swing high ───────
                if level.level_type in ("equal_highs", "swing_high", "session_high"):
                    if row.high > level.price and row.close < level.price:
                        wick_size = row.high - level.price
                        wick_ratio = wick_size / bar_range
                        if wick_ratio >= self.min_wick_ratio:
                            strength = level.strength * wick_ratio
                            if strength > best_strength:
                                best_strength = strength
                                best_sweep = SweepResult(
                                    detected=True,
                                    direction="bearish",
                                    swept_level=level.price,
                                    sweep_low=row.low,
                                    sweep_high=row.high,
                                    reversal_bar=len(df) - check_bars + i,
                                    strength=round(strength, 4),
                                    levels=levels,
                                )

        if best_sweep:
            return best_sweep

        return SweepResult(
            detected=False,
            direction=None,
            swept_level=None,
            sweep_low=None,
            sweep_high=None,
            reversal_bar=None,
            strength=0.0,
            levels=levels,
        )
