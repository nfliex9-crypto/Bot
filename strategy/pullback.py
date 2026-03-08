from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import settings
from core.enums import Direction
from core.models import StructureBreak

logger = logging.getLogger(__name__)


class PullbackDetector:
    """
    Detects pullback entries after a Break of Structure.

    A valid pullback:
    1. Price retraces to the 50-61.8% Fibonacci level of the impulse leg.
    2. Shows rejection (wick / engulfing) at the retracement zone.
    3. Aligns with the BOS direction.
    """

    def __init__(self, fib_level: float = 0.0) -> None:
        self.fib_level = fib_level or settings.pullback_fib_level

    def detect(
        self,
        df: pd.DataFrame,
        bos: StructureBreak,
        swing_low: float,
        swing_high: float,
    ) -> Optional[dict]:
        """
        Returns pullback info dict if a valid entry is found, else None.

        For LONG: impulse leg = swing_low -> bos.price, pullback to 50-61.8%.
        For SHORT: impulse leg = swing_high -> bos.price, pullback to 50-61.8%.
        """
        if df.empty or len(df) < 5:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]

        if bos.direction == Direction.LONG:
            impulse_range = swing_high - swing_low
            if impulse_range <= 0:
                return None
            fib_50 = swing_high - impulse_range * 0.5
            fib_618 = swing_high - impulse_range * self.fib_level

            zone_top = fib_50
            zone_bottom = fib_618

            in_zone = last["low"] <= zone_top and last["close"] >= zone_bottom
            rejection = (
                last["close"] > last["open"]
                and last["lower_wick"] > last["body_size"] * 0.5
            ) if "lower_wick" in df.columns and "body_size" in df.columns else (
                last["close"] > last["open"]
            )

            if in_zone and rejection:
                return {
                    "direction": Direction.LONG,
                    "entry_price": float(last["close"]),
                    "fib_zone_top": float(zone_top),
                    "fib_zone_bottom": float(zone_bottom),
                    "impulse_range": float(impulse_range),
                    "swing_low": swing_low,
                    "swing_high": swing_high,
                }

        elif bos.direction == Direction.SHORT:
            impulse_range = swing_high - swing_low
            if impulse_range <= 0:
                return None
            fib_50 = swing_low + impulse_range * 0.5
            fib_618 = swing_low + impulse_range * self.fib_level

            zone_bottom = fib_50
            zone_top = fib_618

            in_zone = last["high"] >= zone_bottom and last["close"] <= zone_top
            rejection = (
                last["close"] < last["open"]
                and last["upper_wick"] > last["body_size"] * 0.5
            ) if "upper_wick" in df.columns and "body_size" in df.columns else (
                last["close"] < last["open"]
            )

            if in_zone and rejection:
                return {
                    "direction": Direction.SHORT,
                    "entry_price": float(last["close"]),
                    "fib_zone_top": float(zone_top),
                    "fib_zone_bottom": float(zone_bottom),
                    "impulse_range": float(impulse_range),
                    "swing_low": swing_low,
                    "swing_high": swing_high,
                }

        return None
