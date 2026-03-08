"""
Break of Structure (BOS) Detection

Identifies when price breaks a significant swing high/low, indicating a shift in
market structure. A bullish BOS occurs when price breaks above a swing high in a
downtrend; a bearish BOS when price breaks below a swing low in an uptrend.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional

from app.strategy.indicators import (
    find_swing_highs, find_swing_lows, calculate_ema, calculate_atr
)


@dataclass
class StructureBreak:
    direction: str  # "bullish" or "bearish"
    broken_level: float
    break_candle_index: int
    strength: float  # 0.0 to 1.0, based on momentum and volume
    is_change_of_character: bool  # ChoCH = first BOS against the trend
    previous_trend: str  # "bullish", "bearish", or "neutral"
    timestamp: Optional[pd.Timestamp] = None


class BreakOfStructureDetector:
    """Detects break of structure and change of character patterns."""

    def __init__(
        self,
        swing_lookback: int = 10,
        trend_ema_period: int = 50,
        min_break_atr_mult: float = 0.1,
        confirmation_candles: int = 1,
    ):
        self.swing_lookback = swing_lookback
        self.trend_ema_period = trend_ema_period
        self.min_break_atr_mult = min_break_atr_mult
        self.confirmation_candles = confirmation_candles

    def detect(self, df: pd.DataFrame) -> list[StructureBreak]:
        if len(df) < max(self.swing_lookback * 3, self.trend_ema_period + 10):
            return []

        ema = calculate_ema(df["close"], self.trend_ema_period)
        atr = calculate_atr(df)
        swing_highs_mask = find_swing_highs(df, self.swing_lookback)
        swing_lows_mask = find_swing_lows(df, self.swing_lookback)

        swing_high_points = []
        swing_low_points = []

        for i in range(len(df)):
            if swing_highs_mask.iloc[i]:
                swing_high_points.append((i, df["high"].iloc[i]))
            if swing_lows_mask.iloc[i]:
                swing_low_points.append((i, df["low"].iloc[i]))

        breaks = []
        last_trend = "neutral"

        scan_start = max(self.swing_lookback * 2, self.trend_ema_period)

        for i in range(scan_start, len(df)):
            current_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else 0
            if current_atr == 0:
                continue

            current_trend = self._determine_trend(df, ema, i)
            min_break = current_atr * self.min_break_atr_mult

            bullish_bos = self._check_bullish_bos(
                df, i, swing_high_points, min_break, current_trend, last_trend
            )
            if bullish_bos:
                breaks.append(bullish_bos)
                last_trend = "bullish"

            bearish_bos = self._check_bearish_bos(
                df, i, swing_low_points, min_break, current_trend, last_trend
            )
            if bearish_bos:
                breaks.append(bearish_bos)
                last_trend = "bearish"

        return breaks

    def _determine_trend(self, df: pd.DataFrame, ema: pd.Series, idx: int) -> str:
        if pd.isna(ema.iloc[idx]):
            return "neutral"
        close = df["close"].iloc[idx]
        ema_val = ema.iloc[idx]
        pct_diff = (close - ema_val) / ema_val
        if pct_diff > 0.002:
            return "bullish"
        elif pct_diff < -0.002:
            return "bearish"
        return "neutral"

    def _check_bullish_bos(
        self,
        df: pd.DataFrame,
        idx: int,
        swing_high_points: list,
        min_break: float,
        current_trend: str,
        last_trend: str,
    ) -> Optional[StructureBreak]:
        """Check if price breaks above a recent swing high."""
        relevant_highs = [
            (si, sl) for si, sl in swing_high_points
            if si < idx - self.confirmation_candles and si > idx - 100
        ]
        if not relevant_highs:
            return None

        most_recent_high = relevant_highs[-1]
        sh_idx, sh_level = most_recent_high

        candle_close = df["close"].iloc[idx]
        break_amount = candle_close - sh_level

        if break_amount <= min_break:
            return None

        confirmed = True
        for c in range(1, self.confirmation_candles + 1):
            ci = idx - c
            if ci >= 0 and df["close"].iloc[ci] > sh_level:
                confirmed = False
                break

        if not confirmed:
            return None

        body = abs(df["close"].iloc[idx] - df["open"].iloc[idx])
        total_range = df["high"].iloc[idx] - df["low"].iloc[idx]
        momentum = body / total_range if total_range > 0 else 0
        strength = min(1.0, momentum * 1.5)

        is_choch = last_trend == "bearish" or current_trend == "bearish"

        ts = df["timestamp"].iloc[idx] if "timestamp" in df.columns else None

        return StructureBreak(
            direction="bullish",
            broken_level=sh_level,
            break_candle_index=idx,
            strength=strength,
            is_change_of_character=is_choch,
            previous_trend=current_trend,
            timestamp=ts,
        )

    def _check_bearish_bos(
        self,
        df: pd.DataFrame,
        idx: int,
        swing_low_points: list,
        min_break: float,
        current_trend: str,
        last_trend: str,
    ) -> Optional[StructureBreak]:
        """Check if price breaks below a recent swing low."""
        relevant_lows = [
            (si, sl) for si, sl in swing_low_points
            if si < idx - self.confirmation_candles and si > idx - 100
        ]
        if not relevant_lows:
            return None

        most_recent_low = relevant_lows[-1]
        sl_idx, sl_level = most_recent_low

        candle_close = df["close"].iloc[idx]
        break_amount = sl_level - candle_close

        if break_amount <= min_break:
            return None

        confirmed = True
        for c in range(1, self.confirmation_candles + 1):
            ci = idx - c
            if ci >= 0 and df["close"].iloc[ci] < sl_level:
                confirmed = False
                break

        if not confirmed:
            return None

        body = abs(df["close"].iloc[idx] - df["open"].iloc[idx])
        total_range = df["high"].iloc[idx] - df["low"].iloc[idx]
        momentum = body / total_range if total_range > 0 else 0
        strength = min(1.0, momentum * 1.5)

        is_choch = last_trend == "bullish" or current_trend == "bullish"

        ts = df["timestamp"].iloc[idx] if "timestamp" in df.columns else None

        return StructureBreak(
            direction="bearish",
            broken_level=sl_level,
            break_candle_index=idx,
            strength=strength,
            is_change_of_character=is_choch,
            previous_trend=current_trend,
            timestamp=ts,
        )

    def get_latest_bos(
        self, df: pd.DataFrame, lookback_candles: int = 20
    ) -> Optional[StructureBreak]:
        """Get the most recent BOS within the lookback window."""
        breaks = self.detect(df)
        if not breaks:
            return None

        recent = [b for b in breaks if b.break_candle_index >= len(df) - lookback_candles]
        return recent[-1] if recent else None
