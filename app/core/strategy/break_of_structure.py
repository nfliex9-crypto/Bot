"""
Break of Structure (BOS) Detection.

After a liquidity sweep, price should break the opposing swing structure
to confirm the reversal direction.

Bullish BOS: After sweeping lows, price breaks above the last significant swing high
Bearish BOS: After sweeping highs, price breaks below the last significant swing low

BOS vs CHoCH (Change of Character):
- CHoCH: First structural break after a sweep (weaker)
- BOS: Confirmed structural break with a candle close through the level (stronger)
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from app.core.strategy.liquidity_sweep import SweepResult
from app.utils.indicators import find_swing_highs, find_swing_lows, calculate_atr
from app.utils.logger import get_logger

logger = get_logger("break_of_structure")


@dataclass
class BOSResult:
    detected: bool = False
    direction: Optional[str] = None      # "bullish" | "bearish"
    bos_level: Optional[float] = None    # The structure level that was broken
    bos_type: Optional[str] = None       # "choch" | "bos"
    bos_bar_index: Optional[int] = None
    close_beyond: Optional[float] = None # Closing price beyond the BOS level
    strength: float = 0.0                # How far price closed beyond the level (0-1)
    bars_after_sweep: int = 0


class BreakOfStructureDetector:
    """
    Detects Break of Structure following a liquidity sweep.

    After a bullish sweep (lows taken), we expect:
    - Price to form a CHoCH by closing above a recent swing high
    - Followed by a BOS (stronger candle close beyond higher swing high)

    After a bearish sweep (highs taken), we expect:
    - Price to form a CHoCH by closing below a recent swing low
    - Followed by a BOS (stronger candle close beyond lower swing low)
    """

    def __init__(
        self,
        swing_lookback: int = 5,
        max_bars_after_sweep: int = 10,
        min_close_beyond_pct: float = 0.0,  # Minimum close beyond level
    ):
        self.swing_lookback = swing_lookback
        self.max_bars_after_sweep = max_bars_after_sweep
        self.min_close_beyond_pct = min_close_beyond_pct

    def detect(
        self,
        df: pd.DataFrame,
        sweep: SweepResult,
    ) -> BOSResult:
        """
        Detect a break of structure following a liquidity sweep.

        Args:
            df: OHLCV DataFrame
            sweep: Result from LiquiditySweepDetector

        Returns:
            BOSResult with detection details
        """
        if not sweep.detected or sweep.sweep_bar_index is None:
            return BOSResult(detected=False)

        sweep_idx = sweep.sweep_bar_index
        current_idx = len(df) - 1

        if current_idx <= sweep_idx:
            return BOSResult(detected=False)

        atr = calculate_atr(df, 14).iloc[-1]
        bars_after_sweep = current_idx - sweep_idx

        if bars_after_sweep > self.max_bars_after_sweep:
            return BOSResult(detected=False)

        # Get the pre-sweep data to find structure levels
        pre_sweep = df.iloc[max(0, sweep_idx - 30): sweep_idx + 1]
        post_sweep = df.iloc[sweep_idx + 1: current_idx + 1]

        if len(pre_sweep) < self.swing_lookback * 2:
            return BOSResult(detected=False)

        if sweep.direction == "bullish":
            return self._detect_bullish_bos(
                pre_sweep, post_sweep, df, sweep_idx, current_idx, atr, bars_after_sweep
            )
        elif sweep.direction == "bearish":
            return self._detect_bearish_bos(
                pre_sweep, post_sweep, df, sweep_idx, current_idx, atr, bars_after_sweep
            )

        return BOSResult(detected=False)

    def _detect_bullish_bos(
        self,
        pre_sweep: pd.DataFrame,
        post_sweep: pd.DataFrame,
        full_df: pd.DataFrame,
        sweep_idx: int,
        current_idx: int,
        atr: float,
        bars_after_sweep: int,
    ) -> BOSResult:
        """
        After sweeping lows → look for close above recent swing high.
        """
        # Find the most recent swing high before the sweep
        swing_h_mask = find_swing_highs(pre_sweep, self.swing_lookback)
        if not swing_h_mask.any():
            # Fall back to the highest high in pre-sweep window
            bos_level = pre_sweep["high"].max()
        else:
            bos_level = pre_sweep.loc[swing_h_mask, "high"].iloc[-1]

        # Check if any post-sweep bar closed above the BOS level
        for i in range(len(post_sweep)):
            bar = post_sweep.iloc[i]
            if bar["close"] > bos_level:
                close_beyond = bar["close"] - bos_level
                strength = min(close_beyond / (atr + 1e-10), 1.0)
                bos_bar = sweep_idx + 1 + i

                # Classify as CHoCH vs BOS based on strength
                bos_type = "bos" if strength > 0.3 else "choch"

                logger.debug(
                    f"Bullish BOS detected at bar {bos_bar}, level={bos_level:.5f}, "
                    f"close={bar['close']:.5f}, type={bos_type}"
                )
                return BOSResult(
                    detected=True,
                    direction="bullish",
                    bos_level=bos_level,
                    bos_type=bos_type,
                    bos_bar_index=bos_bar,
                    close_beyond=bar["close"],
                    strength=round(strength, 3),
                    bars_after_sweep=bars_after_sweep,
                )

        return BOSResult(detected=False)

    def _detect_bearish_bos(
        self,
        pre_sweep: pd.DataFrame,
        post_sweep: pd.DataFrame,
        full_df: pd.DataFrame,
        sweep_idx: int,
        current_idx: int,
        atr: float,
        bars_after_sweep: int,
    ) -> BOSResult:
        """
        After sweeping highs → look for close below recent swing low.
        """
        # Find the most recent swing low before the sweep
        swing_l_mask = find_swing_lows(pre_sweep, self.swing_lookback)
        if not swing_l_mask.any():
            bos_level = pre_sweep["low"].min()
        else:
            bos_level = pre_sweep.loc[swing_l_mask, "low"].iloc[-1]

        # Check if any post-sweep bar closed below the BOS level
        for i in range(len(post_sweep)):
            bar = post_sweep.iloc[i]
            if bar["close"] < bos_level:
                close_beyond = bos_level - bar["close"]
                strength = min(close_beyond / (atr + 1e-10), 1.0)
                bos_bar = sweep_idx + 1 + i

                bos_type = "bos" if strength > 0.3 else "choch"

                logger.debug(
                    f"Bearish BOS detected at bar {bos_bar}, level={bos_level:.5f}, "
                    f"close={bar['close']:.5f}, type={bos_type}"
                )
                return BOSResult(
                    detected=True,
                    direction="bearish",
                    bos_level=bos_level,
                    bos_type=bos_type,
                    bos_bar_index=bos_bar,
                    close_beyond=bar["close"],
                    strength=round(strength, 3),
                    bars_after_sweep=bars_after_sweep,
                )

        return BOSResult(detected=False)
