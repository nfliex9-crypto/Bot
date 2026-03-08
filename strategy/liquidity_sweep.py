from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import settings
from core.models import Direction, LiquiditySweepSignal, SwingPoint
from utils.helpers import find_swing_highs, find_swing_lows
from utils.logger import get_logger

logger = get_logger(__name__)


def _identify_liquidity_levels(
    df: pd.DataFrame,
    lookback: int,
) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Identify recent swing highs (buy-side liquidity) and
    swing lows (sell-side liquidity) from the OHLCV dataframe.
    """
    swing_high_mask = find_swing_highs(df["high"], lookback=lookback)
    swing_low_mask = find_swing_lows(df["low"], lookback=lookback)

    highs: List[SwingPoint] = []
    lows: List[SwingPoint] = []

    for i in df.index[swing_high_mask]:
        iloc = df.index.get_loc(i)
        highs.append(
            SwingPoint(
                price=df.loc[i, "high"],
                index=iloc,
                timestamp=i if hasattr(i, "to_pydatetime") else df.loc[i, "timestamp"],
                is_high=True,
            )
        )

    for i in df.index[swing_low_mask]:
        iloc = df.index.get_loc(i)
        lows.append(
            SwingPoint(
                price=df.loc[i, "low"],
                index=iloc,
                timestamp=i if hasattr(i, "to_pydatetime") else df.loc[i, "timestamp"],
                is_high=False,
            )
        )

    return highs[-5:], lows[-5:]   # Keep the 5 most recent


def _sweep_detected(
    sweep_candle: pd.Series,
    level: float,
    direction: Direction,
    threshold_pct: float,
) -> bool:
    """
    A sweep is confirmed when:
    - For SHORT (sweep of highs): the wick exceeded the level but closed below it.
    - For LONG  (sweep of lows):  the wick went below the level but closed above it.
    """
    if direction == Direction.SHORT:
        wick_through = sweep_candle["high"] > level * (1 + threshold_pct)
        closed_below = sweep_candle["close"] < level
        return bool(wick_through and closed_below)

    # Direction.LONG
    wick_through = sweep_candle["low"] < level * (1 - threshold_pct)
    closed_above = sweep_candle["close"] > level
    return bool(wick_through and closed_above)


class LiquiditySweepDetector:
    """
    Detects liquidity sweeps on a given OHLCV DataFrame.

    A liquidity sweep occurs when price pierces through a significant
    swing high (buy-side liquidity) or swing low (sell-side liquidity)
    and immediately reverses, indicating institutional accumulation / distribution.
    """

    def __init__(self) -> None:
        self._lookback = settings.swing_lookback
        self._threshold = settings.liquidity_threshold

    # ------------------------------------------------------------------
    def detect(self, df: pd.DataFrame, symbol: str) -> Optional[LiquiditySweepSignal]:
        """
        Analyse the most recent candle for a liquidity sweep.

        df must contain columns: open, high, low, close, volume
        with a DatetimeIndex or a 'timestamp' column.

        Returns a LiquiditySweepSignal if a sweep is detected, else None.
        """
        if len(df) < self._lookback * 2 + 5:
            return None

        # Use all bars except the last one to build liquidity levels
        df_levels = df.iloc[:-1]
        last_candle = df.iloc[-1]
        swing_highs, swing_lows = _identify_liquidity_levels(df_levels, self._lookback)

        # Check for sell-side liquidity sweep (long setup)
        for sl in reversed(swing_lows):
            if _sweep_detected(last_candle, sl.price, Direction.LONG, self._threshold):
                strength = self._calculate_sweep_strength(
                    last_candle, sl.price, Direction.LONG
                )
                sig = LiquiditySweepSignal(
                    symbol=symbol,
                    direction=Direction.LONG,
                    sweep_price=last_candle["low"],
                    liquidity_level=sl.price,
                    reversal_candle_close=last_candle["close"],
                    timestamp=self._get_ts(df, -1),
                    confirmed=True,
                    strength=strength,
                )
                logger.debug(
                    "Liquidity sweep LONG detected on %s at %.5f (sweep of %.5f)",
                    symbol, last_candle["close"], sl.price,
                )
                return sig

        # Check for buy-side liquidity sweep (short setup)
        for sh in reversed(swing_highs):
            if _sweep_detected(last_candle, sh.price, Direction.SHORT, self._threshold):
                strength = self._calculate_sweep_strength(
                    last_candle, sh.price, Direction.SHORT
                )
                sig = LiquiditySweepSignal(
                    symbol=symbol,
                    direction=Direction.SHORT,
                    sweep_price=last_candle["high"],
                    liquidity_level=sh.price,
                    reversal_candle_close=last_candle["close"],
                    timestamp=self._get_ts(df, -1),
                    confirmed=True,
                    strength=strength,
                )
                logger.debug(
                    "Liquidity sweep SHORT detected on %s at %.5f (sweep of %.5f)",
                    symbol, last_candle["close"], sh.price,
                )
                return sig

        return None

    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_sweep_strength(
        candle: pd.Series, level: float, direction: Direction
    ) -> float:
        """
        Sweep strength 0–1 based on:
        - How far price penetrated the level (wick extension)
        - How strong the reversal close was vs. candle range
        """
        candle_range = candle["high"] - candle["low"]
        if candle_range == 0:
            return 0.0

        if direction == Direction.LONG:
            penetration = max(0.0, level - candle["low"])
            reversal = candle["close"] - candle["low"]
        else:
            penetration = max(0.0, candle["high"] - level)
            reversal = candle["high"] - candle["close"]

        pen_score = min(1.0, penetration / (candle_range * 0.5 + 1e-10))
        rev_score = min(1.0, reversal / (candle_range + 1e-10))
        return round((pen_score + rev_score) / 2, 4)

    @staticmethod
    def _get_ts(df: pd.DataFrame, idx: int):
        try:
            return df.index[idx].to_pydatetime()
        except Exception:
            return df.iloc[idx].get("timestamp")
