"""
Strategy Engine

Orchestrates the full analysis pipeline: liquidity sweep detection,
break of structure identification, and pullback entry evaluation.
"""

import pandas as pd
from typing import Optional

from app.strategy.liquidity_sweep import LiquiditySweepDetector
from app.strategy.break_of_structure import BreakOfStructureDetector
from app.strategy.pullback_entry import PullbackEntryModel, TradeSetup
from app.core.logging import get_logger

logger = get_logger(__name__)


class StrategyEngine:
    """Orchestrates the complete SMC-based analysis pipeline."""

    def __init__(self):
        self.sweep_detector = LiquiditySweepDetector()
        self.bos_detector = BreakOfStructureDetector()
        self.pullback_model = PullbackEntryModel()

    async def analyze(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> list[TradeSetup]:
        """Run full analysis pipeline on OHLCV data."""
        if df.empty or len(df) < 60:
            logger.warning("Insufficient data for analysis", symbol=symbol, bars=len(df))
            return []

        logger.info("Running strategy analysis", symbol=symbol, timeframe=timeframe, bars=len(df))

        sweep = self.sweep_detector.get_latest_sweep(df, lookback_candles=15)
        bos = self.bos_detector.get_latest_bos(df, lookback_candles=25)

        if sweep:
            logger.info(
                "Liquidity sweep detected",
                direction=sweep.direction,
                level=sweep.sweep_level,
                strength=sweep.rejection_strength,
            )
        if bos:
            logger.info(
                "Break of structure detected",
                direction=bos.direction,
                level=bos.broken_level,
                is_choch=bos.is_change_of_character,
            )

        setups = self.pullback_model.find_entries(
            df, symbol, timeframe, sweep=sweep, bos=bos
        )

        logger.info("Strategy analysis complete", symbol=symbol, setups_found=len(setups))
        return setups

    async def analyze_multi_timeframe(
        self,
        data: dict[str, pd.DataFrame],
        symbol: str,
    ) -> list[TradeSetup]:
        """Analyze across multiple timeframes for confluence."""
        all_setups = []
        for tf, df in data.items():
            setups = await self.analyze(df, symbol, tf)
            all_setups.extend(setups)

        if len(all_setups) > 1:
            directions = set(s.direction for s in all_setups)
            if len(directions) == 1:
                for s in all_setups:
                    s.confidence = min(1.0, s.confidence * 1.15)
                    s.details["multi_tf_confluence"] = True
                logger.info("Multi-timeframe confluence confirmed", symbol=symbol)

        return all_setups
