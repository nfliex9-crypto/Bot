"""
Liquidity Sweep Detection

Detects when price sweeps above swing highs or below swing lows to grab liquidity
before reversing. This is a key smart-money concept (SMC) pattern where institutional
players trigger stop-loss clusters before moving price in the intended direction.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

from app.strategy.indicators import find_swing_highs, find_swing_lows, calculate_atr


@dataclass
class LiquiditySweep:
    direction: str  # "bullish" (sweep lows then go up) or "bearish" (sweep highs then go down)
    sweep_level: float
    sweep_candle_index: int
    rejection_strength: float  # 0.0 to 1.0
    volume_spike: bool
    wick_ratio: float
    timestamp: Optional[pd.Timestamp] = None


class LiquiditySweepDetector:
    """Detects liquidity sweeps at key swing points."""

    def __init__(
        self,
        swing_lookback: int = 10,
        sweep_threshold_atr_mult: float = 0.3,
        min_rejection_ratio: float = 0.5,
        volume_spike_mult: float = 1.5,
    ):
        self.swing_lookback = swing_lookback
        self.sweep_threshold_atr_mult = sweep_threshold_atr_mult
        self.min_rejection_ratio = min_rejection_ratio
        self.volume_spike_mult = volume_spike_mult

    def detect(self, df: pd.DataFrame) -> list[LiquiditySweep]:
        if len(df) < self.swing_lookback * 3:
            return []

        atr = calculate_atr(df)
        swing_highs = find_swing_highs(df, self.swing_lookback)
        swing_lows = find_swing_lows(df, self.swing_lookback)

        swing_high_levels = df.loc[swing_highs, "high"].values
        swing_low_levels = df.loc[swing_lows, "low"].values

        avg_volume = df["volume"].rolling(20).mean()
        sweeps = []

        scan_start = max(self.swing_lookback * 2, 20)

        for i in range(scan_start, len(df)):
            current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0
            if current_atr == 0:
                continue

            sweep_threshold = current_atr * self.sweep_threshold_atr_mult

            bearish_sweep = self._check_high_sweep(
                df, i, swing_high_levels, sweep_threshold, avg_volume
            )
            if bearish_sweep:
                sweeps.append(bearish_sweep)

            bullish_sweep = self._check_low_sweep(
                df, i, swing_low_levels, sweep_threshold, avg_volume
            )
            if bullish_sweep:
                sweeps.append(bullish_sweep)

        return sweeps

    def _check_high_sweep(
        self,
        df: pd.DataFrame,
        idx: int,
        swing_high_levels: np.ndarray,
        threshold: float,
        avg_volume: pd.Series,
    ) -> Optional[LiquiditySweep]:
        """Check if current candle sweeps above a swing high then rejects."""
        candle_high = df["high"].iloc[idx]
        candle_close = df["close"].iloc[idx]
        candle_open = df["open"].iloc[idx]
        candle_low = df["low"].iloc[idx]

        for level in swing_high_levels:
            penetration = candle_high - level
            if penetration <= 0 or penetration > threshold:
                continue

            body = abs(candle_close - candle_open)
            total_range = candle_high - candle_low
            if total_range == 0:
                continue

            upper_wick = candle_high - max(candle_close, candle_open)
            wick_ratio = upper_wick / total_range

            if wick_ratio < self.min_rejection_ratio:
                continue

            closes_below = candle_close < level

            if closes_below and wick_ratio >= self.min_rejection_ratio:
                vol_spike = False
                if not pd.isna(avg_volume.iloc[idx]) and avg_volume.iloc[idx] > 0:
                    vol_spike = df["volume"].iloc[idx] > avg_volume.iloc[idx] * self.volume_spike_mult

                rejection_strength = min(1.0, wick_ratio * (1 + (0.3 if vol_spike else 0)))
                ts = df["timestamp"].iloc[idx] if "timestamp" in df.columns else None

                return LiquiditySweep(
                    direction="bearish",
                    sweep_level=level,
                    sweep_candle_index=idx,
                    rejection_strength=rejection_strength,
                    volume_spike=vol_spike,
                    wick_ratio=wick_ratio,
                    timestamp=ts,
                )
        return None

    def _check_low_sweep(
        self,
        df: pd.DataFrame,
        idx: int,
        swing_low_levels: np.ndarray,
        threshold: float,
        avg_volume: pd.Series,
    ) -> Optional[LiquiditySweep]:
        """Check if current candle sweeps below a swing low then rejects."""
        candle_low = df["low"].iloc[idx]
        candle_close = df["close"].iloc[idx]
        candle_open = df["open"].iloc[idx]
        candle_high = df["high"].iloc[idx]

        for level in swing_low_levels:
            penetration = level - candle_low
            if penetration <= 0 or penetration > threshold:
                continue

            body = abs(candle_close - candle_open)
            total_range = candle_high - candle_low
            if total_range == 0:
                continue

            lower_wick = min(candle_close, candle_open) - candle_low
            wick_ratio = lower_wick / total_range

            if wick_ratio < self.min_rejection_ratio:
                continue

            closes_above = candle_close > level

            if closes_above and wick_ratio >= self.min_rejection_ratio:
                vol_spike = False
                if not pd.isna(avg_volume.iloc[idx]) and avg_volume.iloc[idx] > 0:
                    vol_spike = df["volume"].iloc[idx] > avg_volume.iloc[idx] * self.volume_spike_mult

                rejection_strength = min(1.0, wick_ratio * (1 + (0.3 if vol_spike else 0)))
                ts = df["timestamp"].iloc[idx] if "timestamp" in df.columns else None

                return LiquiditySweep(
                    direction="bullish",
                    sweep_level=level,
                    sweep_candle_index=idx,
                    rejection_strength=rejection_strength,
                    volume_spike=vol_spike,
                    wick_ratio=wick_ratio,
                    timestamp=ts,
                )
        return None

    def get_latest_sweep(self, df: pd.DataFrame, lookback_candles: int = 10) -> Optional[LiquiditySweep]:
        """Get the most recent liquidity sweep within lookback window."""
        sweeps = self.detect(df)
        if not sweeps:
            return None

        recent = [s for s in sweeps if s.sweep_candle_index >= len(df) - lookback_candles]
        return recent[-1] if recent else None
