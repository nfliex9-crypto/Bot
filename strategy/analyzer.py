from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from config.settings import settings
from core.models import (
    Direction,
    MarketBias,
    MultiTimeframeAnalysis,
    TrendStructure,
)
from strategy.break_of_structure import BreakOfStructureDetector
from strategy.liquidity_sweep import LiquiditySweepDetector
from strategy.pullback_entry import PullbackEntryDetector
from utils.logger import get_logger

logger = get_logger(__name__)


class MultiTimeframeAnalyzer:
    """
    Orchestrates multi-timeframe analysis:
      H1  → market bias (bullish / bearish / neutral)
      M15 → trend structure confirmation
      M5  → entry signal (sweep + BOS + pullback)

    Returns a MultiTimeframeAnalysis object with alignment flag.
    """

    def __init__(self) -> None:
        self._bos = BreakOfStructureDetector()
        self._sweep = LiquiditySweepDetector()
        self._pullback = PullbackEntryDetector()

    # ------------------------------------------------------------------
    def analyse(
        self,
        symbol: str,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
    ) -> MultiTimeframeAnalysis:

        mta = MultiTimeframeAnalysis(
            symbol=symbol,
            timestamp=m5_df.index[-1] if not m5_df.empty else pd.Timestamp.utcnow(),
        )

        # ── H1: Market bias ───────────────────────────────────────────
        if len(h1_df) >= settings.swing_lookback * 2:
            mta.h1_bias = self._bos.market_bias(h1_df)
        else:
            mta.h1_bias = MarketBias.NEUTRAL

        # ── M15: Trend structure ──────────────────────────────────────
        if len(m15_df) >= settings.swing_lookback * 2:
            mta.m15_structure = self._bos.trend_structure(m15_df)
        else:
            mta.m15_structure = TrendStructure.RANGING

        # ── M5: Execution signals ─────────────────────────────────────
        if len(m5_df) >= settings.swing_lookback * 2 + 5:
            # 1. Liquidity sweep
            sweep_sig = self._sweep.detect(m5_df, symbol)
            if sweep_sig and sweep_sig.confirmed:
                mta.sweep_signal = sweep_sig

            # 2. Break of Structure
            bos_sig = self._bos.detect(m5_df, symbol)
            if bos_sig and bos_sig.confirmed:
                mta.bos_signal = bos_sig

            # 3. Pullback entry (requires BOS)
            if mta.bos_signal:
                pb_sig = self._pullback.detect(m5_df, symbol, mta.bos_signal)
                if pb_sig and pb_sig.valid:
                    mta.pullback_signal = pb_sig

        # ── Alignment check ───────────────────────────────────────────
        mta.aligned = mta.is_bullish_aligned() or mta.is_bearish_aligned()

        if mta.aligned:
            logger.info(
                "MTF aligned on %s | H1:%s | M15:%s | sweep:%s | bos:%s | pullback:%s",
                symbol,
                mta.h1_bias.value,
                mta.m15_structure.value,
                mta.sweep_signal.direction.value if mta.sweep_signal else "none",
                mta.bos_signal.direction.value if mta.bos_signal else "none",
                mta.pullback_signal.direction.value if mta.pullback_signal else "none",
            )

        return mta

    def get_trade_direction(self, mta: MultiTimeframeAnalysis) -> Optional[Direction]:
        if mta.is_bullish_aligned():
            return Direction.LONG
        if mta.is_bearish_aligned():
            return Direction.SHORT
        return None
