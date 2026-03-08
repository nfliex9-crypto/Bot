"""
Pullback Entry Finder.

After a Liquidity Sweep + Break of Structure, wait for price to pull back
into a key confluence zone for a high-probability entry.

Entry zones (in priority order):
1. Fair Value Gap (FVG) from the impulse move
2. Order Block (OB) that preceded the BOS
3. 50% retracement of the impulse
4. Previous BOS level (now acting as S/R)

Stop Loss options:
1. ATR-based: entry ± (ATR_multiplier × ATR)
2. Structure-based: just below the sweep low / above the sweep high

Take Profit levels:
- TP1: 1R
- TP2: 1.5R
- TP3: 2R
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from app.core.strategy.liquidity_sweep import SweepResult
from app.core.strategy.break_of_structure import BOSResult
from app.utils.indicators import (
    find_fair_value_gaps,
    find_order_blocks,
    calculate_atr,
)
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("pullback_entry")


@dataclass
class EntryResult:
    valid: bool = False
    direction: Optional[str] = None      # "long" | "short"
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    risk_amount_pips: Optional[float] = None
    risk_reward: Optional[float] = None
    entry_zone_type: Optional[str] = None  # "fvg" | "ob" | "50pct" | "bos_level"
    entry_zone_top: Optional[float] = None
    entry_zone_bottom: Optional[float] = None
    atr: Optional[float] = None
    sl_type: Optional[str] = None         # "atr" | "structure"
    confidence_boost: float = 0.0         # Extra confidence for confluence


class PullbackEntryFinder:
    """
    Finds valid pullback entries after a liquidity sweep + BOS sequence.
    """

    def __init__(
        self,
        atr_sl_multiplier: float = 1.5,
        use_structure_sl: bool = True,
        min_rr: float = 1.5,
        tp1_ratio: float = 1.0,
        tp2_ratio: float = 1.5,
        tp3_ratio: float = 2.0,
        fvg_min_atr_ratio: float = 0.3,
    ):
        self.atr_sl_multiplier = atr_sl_multiplier
        self.use_structure_sl = use_structure_sl
        self.min_rr = min_rr
        self.tp1_ratio = tp1_ratio
        self.tp2_ratio = tp2_ratio
        self.tp3_ratio = tp3_ratio
        self.fvg_min_atr_ratio = fvg_min_atr_ratio

    def find_entry(
        self,
        df: pd.DataFrame,
        sweep: SweepResult,
        bos: BOSResult,
    ) -> EntryResult:
        """
        Find a valid pullback entry given sweep and BOS results.

        Args:
            df: OHLCV DataFrame (M5 execution timeframe)
            sweep: Liquidity sweep result
            bos: Break of structure result

        Returns:
            EntryResult with full trade setup
        """
        if not sweep.detected or not bos.detected:
            return EntryResult(valid=False)

        if bos.direction not in ("bullish", "bearish"):
            return EntryResult(valid=False)

        atr = calculate_atr(df, 14).iloc[-1]
        direction = "long" if bos.direction == "bullish" else "short"

        # Find entry zone
        entry_zone = self._find_entry_zone(df, sweep, bos, direction, atr)
        if entry_zone is None:
            return EntryResult(valid=False)

        entry_price, zone_type, zone_top, zone_bottom, confidence_boost = entry_zone

        # Calculate stop loss
        sl = self._calculate_stop_loss(sweep, bos, entry_price, direction, atr, df)
        if sl is None:
            return EntryResult(valid=False)

        sl_type = "structure" if self.use_structure_sl else "atr"
        risk = abs(entry_price - sl)

        if risk <= 0:
            return EntryResult(valid=False)

        # Calculate take profits
        if direction == "long":
            tp1 = entry_price + risk * self.tp1_ratio
            tp2 = entry_price + risk * self.tp2_ratio
            tp3 = entry_price + risk * self.tp3_ratio
        else:
            tp1 = entry_price - risk * self.tp1_ratio
            tp2 = entry_price - risk * self.tp2_ratio
            tp3 = entry_price - risk * self.tp3_ratio

        rr = (abs(tp2 - entry_price)) / risk

        if rr < self.min_rr:
            logger.debug(f"Setup rejected: R:R {rr:.2f} < minimum {self.min_rr}")
            return EntryResult(valid=False)

        logger.info(
            f"Entry found: {direction} @ {entry_price:.5f} "
            f"SL={sl:.5f} TP1={tp1:.5f} RR={rr:.2f} zone={zone_type}"
        )

        return EntryResult(
            valid=True,
            direction=direction,
            entry_price=entry_price,
            stop_loss=sl,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            risk_amount_pips=risk,
            risk_reward=round(rr, 2),
            entry_zone_type=zone_type,
            entry_zone_top=zone_top,
            entry_zone_bottom=zone_bottom,
            atr=atr,
            sl_type=sl_type,
            confidence_boost=confidence_boost,
        )

    def _find_entry_zone(
        self,
        df: pd.DataFrame,
        sweep: SweepResult,
        bos: BOSResult,
        direction: str,
        atr: float,
    ) -> Optional[Tuple[float, str, float, float, float]]:
        """
        Find the best entry zone. Returns (entry_price, zone_type, top, bottom, confidence).
        Priority: FVG > OB > 50% retracement > BOS level
        """
        current_price = df.iloc[-1]["close"]

        # 1. Fair Value Gap
        fvgs = find_fair_value_gaps(df, self.fvg_min_atr_ratio)
        if not fvgs.empty:
            if direction == "long":
                bullish_fvgs = fvgs[fvgs["type"] == "bullish_fvg"].copy()
                # FVG should be below current price (pullback into it)
                bullish_fvgs = bullish_fvgs[bullish_fvgs["top"] < current_price]
                if not bullish_fvgs.empty:
                    best = bullish_fvgs.iloc[-1]
                    entry = best["mid"]
                    return (entry, "fvg", best["top"], best["bottom"], 0.1)

            elif direction == "short":
                bearish_fvgs = fvgs[fvgs["type"] == "bearish_fvg"].copy()
                bearish_fvgs = bearish_fvgs[bearish_fvgs["bottom"] > current_price]
                if not bearish_fvgs.empty:
                    best = bearish_fvgs.iloc[-1]
                    entry = best["mid"]
                    return (entry, "fvg", best["top"], best["bottom"], 0.1)

        # 2. Order Block
        ob_direction = "bullish" if direction == "long" else "bearish"
        obs = find_order_blocks(df, ob_direction, lookback=30)
        if not obs.empty:
            if direction == "long":
                valid_obs = obs[obs["top"] < current_price]
                if not valid_obs.empty:
                    best = valid_obs.iloc[-1]
                    entry = best["mid"]
                    return (entry, "ob", best["top"], best["bottom"], 0.05)

            elif direction == "short":
                valid_obs = obs[obs["bottom"] > current_price]
                if not valid_obs.empty:
                    best = valid_obs.iloc[-1]
                    entry = best["mid"]
                    return (entry, "ob", best["top"], best["bottom"], 0.05)

        # 3. 50% retracement of impulse
        if bos.bos_bar_index is not None and sweep.sweep_bar_index is not None:
            impulse_slice = df.iloc[sweep.sweep_bar_index: bos.bos_bar_index + 1]
            if len(impulse_slice) >= 2:
                if direction == "long":
                    impulse_low = impulse_slice["low"].min()
                    impulse_high = impulse_slice["high"].max()
                    retrace_50 = impulse_low + (impulse_high - impulse_low) * 0.5
                    if current_price > retrace_50:
                        zone_size = atr * 0.5
                        return (retrace_50, "50pct", retrace_50 + zone_size, retrace_50 - zone_size, 0.0)
                else:
                    impulse_low = impulse_slice["low"].min()
                    impulse_high = impulse_slice["high"].max()
                    retrace_50 = impulse_high - (impulse_high - impulse_low) * 0.5
                    if current_price < retrace_50:
                        zone_size = atr * 0.5
                        return (retrace_50, "50pct", retrace_50 + zone_size, retrace_50 - zone_size, 0.0)

        # 4. BOS level as entry
        if bos.bos_level is not None:
            zone_size = atr * 0.3
            return (bos.bos_level, "bos_level", bos.bos_level + zone_size, bos.bos_level - zone_size, 0.0)

        return None

    def _calculate_stop_loss(
        self,
        sweep: SweepResult,
        bos: BOSResult,
        entry_price: float,
        direction: str,
        atr: float,
        df: pd.DataFrame,
    ) -> Optional[float]:
        """
        Calculate stop loss. Uses structure SL if enabled (below sweep wick),
        otherwise uses ATR-based SL.
        """
        buffer = atr * 0.2  # Small buffer beyond structure

        if self.use_structure_sl:
            if direction == "long" and sweep.sweep_low is not None:
                sl = sweep.sweep_low - buffer
            elif direction == "short" and sweep.sweep_high is not None:
                sl = sweep.sweep_high + buffer
            else:
                # Fall back to ATR
                sl = self._atr_sl(entry_price, direction, atr)
        else:
            sl = self._atr_sl(entry_price, direction, atr)

        # Sanity check: SL must be on correct side of entry
        if direction == "long" and sl >= entry_price:
            return None
        if direction == "short" and sl <= entry_price:
            return None

        return sl

    def _atr_sl(self, entry_price: float, direction: str, atr: float) -> float:
        """ATR-based stop loss."""
        if direction == "long":
            return entry_price - atr * self.atr_sl_multiplier
        else:
            return entry_price + atr * self.atr_sl_multiplier
