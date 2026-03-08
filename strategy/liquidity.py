"""
Liquidity sweep detection: identifies equal highs/lows, liquidity pools,
and sweep events that precede reversals.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

import numpy as np
import pandas as pd

from core.logger import get_logger
from core.models import LiquidityZone, SwingPoint

logger = get_logger("strategy.liquidity")


class LiquidityAnalyzer:
    def __init__(self, lookback: int = 50, tolerance_pct: float = 0.0005):
        self.lookback = lookback
        self.tolerance_pct = tolerance_pct

    def find_liquidity_zones(
        self, df: pd.DataFrame, swings: List[SwingPoint]
    ) -> List[LiquidityZone]:
        """
        Identify liquidity zones: clusters of equal highs/lows where
        stop-losses accumulate.
        """
        zones = []
        highs = [s for s in swings if s.is_high]
        lows = [s for s in swings if not s.is_high]

        zones.extend(self._find_equal_levels(highs, "sell_side"))
        zones.extend(self._find_equal_levels(lows, "buy_side"))
        zones.extend(self._find_session_extremes(df))

        return zones

    def _find_equal_levels(
        self, points: List[SwingPoint], zone_type: str
    ) -> List[LiquidityZone]:
        """Cluster nearby swing points as equal highs or equal lows."""
        if len(points) < 2:
            return []

        zones = []
        used = set()

        for i in range(len(points)):
            if i in used:
                continue
            cluster = [points[i]]
            for j in range(i + 1, len(points)):
                if j in used:
                    continue
                pct_diff = abs(points[i].price - points[j].price) / points[i].price
                if pct_diff <= self.tolerance_pct:
                    cluster.append(points[j])
                    used.add(j)

            if len(cluster) >= 2:
                avg_price = np.mean([p.price for p in cluster])
                zones.append(LiquidityZone(
                    price_level=float(avg_price),
                    zone_type=zone_type,
                    strength=len(cluster),
                    touch_count=len(cluster),
                    timestamp=cluster[-1].timestamp,
                ))
                used.add(i)

        return zones

    def _find_session_extremes(self, df: pd.DataFrame) -> List[LiquidityZone]:
        """Previous session highs/lows are natural liquidity targets."""
        zones = []
        if len(df) < 24:
            return zones

        recent = df.tail(min(100, len(df)))
        if "timestamp" not in recent.columns:
            return zones

        recent = recent.copy()
        recent["date"] = pd.to_datetime(recent["timestamp"]).dt.date
        daily = recent.groupby("date").agg({"high": "max", "low": "min"}).reset_index()

        if len(daily) >= 2:
            prev_day = daily.iloc[-2]
            zones.append(LiquidityZone(
                price_level=float(prev_day["high"]),
                zone_type="sell_side",
                strength=2,
                timestamp=datetime.utcnow(),
            ))
            zones.append(LiquidityZone(
                price_level=float(prev_day["low"]),
                zone_type="buy_side",
                strength=2,
                timestamp=datetime.utcnow(),
            ))

        return zones

    def detect_sweep(
        self, df: pd.DataFrame, zones: List[LiquidityZone]
    ) -> List[Tuple[LiquidityZone, str]]:
        """
        Detect if price swept a liquidity zone and reversed.
        Returns list of (zone, sweep_direction) tuples.
        """
        sweeps = []
        if len(df) < 3:
            return sweeps

        last_candles = df.tail(5)

        for zone in zones:
            if zone.swept:
                continue

            for _, candle in last_candles.iterrows():
                if zone.zone_type == "sell_side":
                    if candle["high"] > zone.price_level and candle["close"] < zone.price_level:
                        zone.swept = True
                        sweeps.append((zone, "bearish_sweep"))
                        logger.info(
                            f"Bearish liquidity sweep at {zone.price_level:.5f}"
                        )
                        break

                elif zone.zone_type == "buy_side":
                    if candle["low"] < zone.price_level and candle["close"] > zone.price_level:
                        zone.swept = True
                        sweeps.append((zone, "bullish_sweep"))
                        logger.info(
                            f"Bullish liquidity sweep at {zone.price_level:.5f}"
                        )
                        break

        return sweeps
