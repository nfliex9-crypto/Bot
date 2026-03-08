from __future__ import annotations

import logging
from typing import List

import numpy as np
import pandas as pd

from config.settings import settings
from core.models import LiquidityZone, SwingPoint

logger = logging.getLogger(__name__)


class LiquidityAnalyzer:
    """Detects liquidity zones and sweeps (stop hunts beyond swing points)."""

    def __init__(self, lookback: int = 0, atr_mult: float = 0.0) -> None:
        self.lookback = lookback or settings.swing_lookback
        self.atr_mult = atr_mult or settings.liquidity_zone_atr_mult

    def find_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        swings: List[SwingPoint] = []
        highs = df["high"].values
        n = self.lookback
        for i in range(n, len(highs) - n):
            if highs[i] == max(highs[i - n: i + n + 1]):
                swings.append(SwingPoint(
                    timestamp=df.index[i],
                    price=float(highs[i]),
                    is_high=True,
                    index=i,
                ))
        return swings

    def find_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        swings: List[SwingPoint] = []
        lows = df["low"].values
        n = self.lookback
        for i in range(n, len(lows) - n):
            if lows[i] == min(lows[i - n: i + n + 1]):
                swings.append(SwingPoint(
                    timestamp=df.index[i],
                    price=float(lows[i]),
                    is_high=False,
                    index=i,
                ))
        return swings

    def detect_liquidity_zones(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """Build liquidity zones around clusters of swing highs/lows."""
        zones: List[LiquidityZone] = []
        if df.empty or "atr" not in df.columns:
            return zones

        swing_highs = self.find_swing_highs(df)
        swing_lows = self.find_swing_lows(df)
        atr = df["atr"].iloc[-1] if not np.isnan(df["atr"].iloc[-1]) else 0.0
        zone_width = atr * self.atr_mult

        for sh in swing_highs[-10:]:
            zones.append(LiquidityZone(
                price_level=sh.price,
                zone_high=sh.price + zone_width,
                zone_low=sh.price - zone_width * 0.3,
                touches=self._count_touches(df, sh.price, zone_width),
                swept=False,
                timestamp=sh.timestamp,
                timeframe=df.iloc[0].get("timeframe", "") if "timeframe" in df.columns else "",
            ))

        for sl in swing_lows[-10:]:
            zones.append(LiquidityZone(
                price_level=sl.price,
                zone_high=sl.price + zone_width * 0.3,
                zone_low=sl.price - zone_width,
                touches=self._count_touches(df, sl.price, zone_width),
                swept=False,
                timestamp=sl.timestamp,
                timeframe=df.iloc[0].get("timeframe", "") if "timeframe" in df.columns else "",
            ))
        return zones

    def detect_sweep(
        self, df: pd.DataFrame, zones: List[LiquidityZone]
    ) -> List[LiquidityZone]:
        """
        A liquidity sweep occurs when price wicks beyond a zone then closes back
        inside, indicating stop-hunt / liquidity grab.
        """
        if df.empty or len(df) < 3:
            return []
        swept: List[LiquidityZone] = []
        last = df.iloc[-1]
        prev = df.iloc[-2]

        for zone in zones:
            if zone.swept:
                continue
            if zone.price_level > last["close"]:
                if last["high"] > zone.zone_high and last["close"] < zone.price_level:
                    zone.swept = True
                    swept.append(zone)
            else:
                if last["low"] < zone.zone_low and last["close"] > zone.price_level:
                    zone.swept = True
                    swept.append(zone)
        return swept

    @staticmethod
    def _count_touches(df: pd.DataFrame, level: float, tolerance: float) -> int:
        touches = ((df["high"] >= level - tolerance) & (df["low"] <= level + tolerance)).sum()
        return int(touches)
