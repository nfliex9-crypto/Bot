from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import settings
from core.enums import Bias, Direction
from core.models import StructureBreak, SwingPoint
from strategy.liquidity import LiquidityAnalyzer

logger = logging.getLogger(__name__)


class StructureAnalyzer:
    """Detects Break of Structure (BOS) and Change of Character (CHoCH)."""

    def __init__(self, lookback: int = 0) -> None:
        self.lookback = lookback or settings.structure_lookback
        self._liq = LiquidityAnalyzer()

    def determine_bias(self, df: pd.DataFrame) -> Bias:
        """
        H1 bias: bullish if making higher highs + higher lows,
        bearish if lower highs + lower lows.
        """
        if df.empty or len(df) < self.lookback:
            return Bias.NEUTRAL

        swing_highs = self._liq.find_swing_highs(df)
        swing_lows = self._liq.find_swing_lows(df)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return Bias.NEUTRAL

        hh = swing_highs[-1].price > swing_highs[-2].price
        hl = swing_lows[-1].price > swing_lows[-2].price
        lh = swing_highs[-1].price < swing_highs[-2].price
        ll = swing_lows[-1].price < swing_lows[-2].price

        if hh and hl:
            return Bias.BULLISH
        elif lh and ll:
            return Bias.BEARISH

        ema_20 = df["ema_20"].iloc[-1] if "ema_20" in df.columns else None
        ema_50 = df["ema_50"].iloc[-1] if "ema_50" in df.columns else None
        if ema_20 is not None and ema_50 is not None:
            if not np.isnan(ema_20) and not np.isnan(ema_50):
                if ema_20 > ema_50:
                    return Bias.BULLISH
                elif ema_20 < ema_50:
                    return Bias.BEARISH

        return Bias.NEUTRAL

    def detect_bos(self, df: pd.DataFrame) -> Optional[StructureBreak]:
        """
        Break of Structure: price closes beyond the most recent swing point
        in the direction of the prevailing trend.
        """
        if df.empty or len(df) < self.lookback:
            return None

        swing_highs = self._liq.find_swing_highs(df)
        swing_lows = self._liq.find_swing_lows(df)
        last = df.iloc[-1]

        if swing_highs and last["close"] > swing_highs[-1].price:
            return StructureBreak(
                timestamp=last.name if hasattr(last, "name") else df.index[-1],
                price=float(last["close"]),
                direction=Direction.LONG,
                broken_level=swing_highs[-1].price,
                timeframe=last.get("timeframe", "") if isinstance(last, dict) else "",
            )

        if swing_lows and last["close"] < swing_lows[-1].price:
            return StructureBreak(
                timestamp=last.name if hasattr(last, "name") else df.index[-1],
                price=float(last["close"]),
                direction=Direction.SHORT,
                broken_level=swing_lows[-1].price,
                timeframe=last.get("timeframe", "") if isinstance(last, dict) else "",
            )
        return None

    def detect_choch(self, df: pd.DataFrame, current_bias: Bias) -> Optional[StructureBreak]:
        """
        Change of Character: a BOS that goes against the current bias,
        signaling a potential trend reversal.
        """
        bos = self.detect_bos(df)
        if bos is None:
            return None

        if current_bias == Bias.BULLISH and bos.direction == Direction.SHORT:
            return bos
        if current_bias == Bias.BEARISH and bos.direction == Direction.LONG:
            return bos
        return None

    def get_structure_levels(
        self, df: pd.DataFrame
    ) -> Tuple[List[float], List[float]]:
        """Return recent resistance and support levels."""
        swing_highs = self._liq.find_swing_highs(df)
        swing_lows = self._liq.find_swing_lows(df)
        resistances = [s.price for s in swing_highs[-5:]]
        supports = [s.price for s in swing_lows[-5:]]
        return resistances, supports
