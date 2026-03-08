"""
Multi-Timeframe Analysis (MTF).

Hierarchy:
- H1  → Market Bias (bullish / bearish / neutral)
- M15 → Trend Structure (confirm bias, identify key S/R levels)
- M5  → Execution (Sweep + BOS + Pullback)

The MTF confirms we are trading WITH the higher-timeframe bias.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict
from app.utils.indicators import (
    calculate_ema,
    calculate_atr,
    find_swing_highs,
    find_swing_lows,
    add_all_indicators,
)
from app.core.strategy.liquidity_sweep import LiquiditySweepDetector, SweepResult
from app.core.strategy.break_of_structure import BreakOfStructureDetector, BOSResult
from app.core.strategy.pullback_entry import PullbackEntryFinder, EntryResult
from app.utils.logger import get_logger

logger = get_logger("multi_timeframe")


@dataclass
class MTFAnalysis:
    symbol: str = ""

    # H1 Bias
    h1_bias: str = "neutral"          # bullish | bearish | neutral
    h1_ema_trend: str = "neutral"
    h1_structure: str = "neutral"
    h1_key_level: Optional[float] = None

    # M15 Trend
    m15_trend: str = "neutral"
    m15_sweep: Optional[SweepResult] = None
    m15_bos: Optional[BOSResult] = None
    m15_aligned: bool = False

    # M5 Execution
    m5_sweep: Optional[SweepResult] = None
    m5_bos: Optional[BOSResult] = None
    m5_entry: Optional[EntryResult] = None

    # Overall assessment
    tradeable: bool = False
    alignment_score: float = 0.0       # 0-1 alignment across timeframes
    setup_quality: str = "poor"        # excellent | good | fair | poor


class MultiTimeframeAnalyzer:
    """
    Coordinates analysis across H1, M15, and M5 timeframes.

    The workflow:
    1. H1: Determine bias (bullish/bearish) using EMA structure + swing analysis
    2. M15: Confirm bias + look for sweep/BOS on the trend structure
    3. M5: Find precise entry after sweep+BOS aligned with higher TF bias
    """

    def __init__(self):
        self.sweep_detector = LiquiditySweepDetector(
            lookback=30,
            swing_lookback=5,
            max_bars_since_sweep=8,
        )
        self.bos_detector = BreakOfStructureDetector(
            swing_lookback=5,
            max_bars_after_sweep=12,
        )
        self.entry_finder = PullbackEntryFinder(
            atr_sl_multiplier=1.5,
            use_structure_sl=True,
            min_rr=1.5,
            tp1_ratio=1.0,
            tp2_ratio=1.5,
            tp3_ratio=2.0,
        )

    def analyze(
        self,
        symbol: str,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
    ) -> MTFAnalysis:
        """
        Run full multi-timeframe analysis.

        Args:
            symbol: Trading symbol
            h1_df: H1 OHLCV DataFrame
            m15_df: M15 OHLCV DataFrame
            m5_df: M5 OHLCV DataFrame

        Returns:
            MTFAnalysis with complete assessment
        """
        result = MTFAnalysis(symbol=symbol)

        # Step 1: H1 Market Bias
        h1_analysis = self._analyze_h1(h1_df)
        result.h1_bias = h1_analysis["bias"]
        result.h1_ema_trend = h1_analysis["ema_trend"]
        result.h1_structure = h1_analysis["structure"]
        result.h1_key_level = h1_analysis.get("key_level")

        if result.h1_bias == "neutral":
            logger.debug(f"{symbol}: H1 bias neutral, skipping")
            result.tradeable = False
            return result

        # Step 2: M15 Trend Structure
        m15_analysis = self._analyze_m15(m15_df, result.h1_bias)
        result.m15_trend = m15_analysis["trend"]
        result.m15_sweep = m15_analysis.get("sweep")
        result.m15_bos = m15_analysis.get("bos")
        result.m15_aligned = m15_analysis["aligned"]

        # Step 3: M5 Execution (only if M15 is aligned with H1)
        if result.m15_aligned:
            m5_analysis = self._analyze_m5(m5_df, result.h1_bias)
            result.m5_sweep = m5_analysis.get("sweep")
            result.m5_bos = m5_analysis.get("bos")
            result.m5_entry = m5_analysis.get("entry")

        # Compute alignment score and decide if tradeable
        result.alignment_score = self._compute_alignment_score(result)
        result.tradeable = self._is_tradeable(result)
        result.setup_quality = self._rate_setup(result)

        logger.info(
            f"{symbol} MTF: H1={result.h1_bias} M15={result.m15_trend} "
            f"aligned={result.m15_aligned} tradeable={result.tradeable} "
            f"quality={result.setup_quality} score={result.alignment_score:.2f}"
        )

        return result

    def _analyze_h1(self, df: pd.DataFrame) -> dict:
        """Determine H1 market bias."""
        if len(df) < 50:
            return {"bias": "neutral", "ema_trend": "neutral", "structure": "neutral"}

        df = add_all_indicators(df)
        last = df.iloc[-1]

        # EMA-based trend
        ema_21 = last["ema_21"]
        ema_50 = last["ema_50"]
        ema_200 = last.get("ema_200", None)
        close = last["close"]

        ema_bullish = ema_21 > ema_50 and close > ema_21
        ema_bearish = ema_21 < ema_50 and close < ema_21

        if ema_200 is not None and not pd.isna(ema_200):
            ema_bullish = ema_bullish and close > ema_200
            ema_bearish = ema_bearish and close < ema_200

        ema_trend = "bullish" if ema_bullish else ("bearish" if ema_bearish else "neutral")

        # Structure-based trend (higher highs + higher lows = bullish)
        swing_h = find_swing_highs(df, 8)
        swing_l = find_swing_lows(df, 8)

        structure = "neutral"
        if swing_h.sum() >= 2 and swing_l.sum() >= 2:
            recent_highs = df.loc[swing_h, "high"].values[-3:]
            recent_lows = df.loc[swing_l, "low"].values[-3:]

            hh = all(recent_highs[i] < recent_highs[i + 1] for i in range(len(recent_highs) - 1))
            hl = all(recent_lows[i] < recent_lows[i + 1] for i in range(len(recent_lows) - 1))
            lh = all(recent_highs[i] > recent_highs[i + 1] for i in range(len(recent_highs) - 1))
            ll = all(recent_lows[i] > recent_lows[i + 1] for i in range(len(recent_lows) - 1))

            if hh and hl:
                structure = "bullish"
            elif lh and ll:
                structure = "bearish"

        # Combine signals
        signals = [ema_trend, structure]
        bullish_count = signals.count("bullish")
        bearish_count = signals.count("bearish")

        if bullish_count > bearish_count:
            bias = "bullish"
        elif bearish_count > bullish_count:
            bias = "bearish"
        else:
            bias = "neutral"

        # Key level: most recent swing high (for bearish) or swing low (for bullish)
        key_level = None
        if bias == "bullish" and swing_l.any():
            key_level = df.loc[swing_l, "low"].iloc[-1]
        elif bias == "bearish" and swing_h.any():
            key_level = df.loc[swing_h, "high"].iloc[-1]

        return {
            "bias": bias,
            "ema_trend": ema_trend,
            "structure": structure,
            "key_level": key_level,
        }

    def _analyze_m15(self, df: pd.DataFrame, h1_bias: str) -> dict:
        """Analyze M15 for trend confirmation and sweep/BOS."""
        if len(df) < 40:
            return {"trend": "neutral", "aligned": False}

        df = add_all_indicators(df)
        last = df.iloc[-1]

        # Quick trend check via EMA
        ema_9 = last["ema_9"]
        ema_21 = last["ema_21"]
        close = last["close"]

        if close > ema_9 > ema_21:
            m15_trend = "bullish"
        elif close < ema_9 < ema_21:
            m15_trend = "bearish"
        else:
            m15_trend = "neutral"

        # Check alignment with H1
        aligned = (h1_bias == "bullish" and m15_trend in ("bullish", "neutral")) or \
                  (h1_bias == "bearish" and m15_trend in ("bearish", "neutral"))

        # Run sweep + BOS on M15
        sweep = self.sweep_detector.detect(df)
        bos = None
        if sweep.detected:
            bos = self.bos_detector.detect(df, sweep)

        return {
            "trend": m15_trend,
            "aligned": aligned,
            "sweep": sweep if sweep.detected else None,
            "bos": bos if (bos and bos.detected) else None,
        }

    def _analyze_m5(self, df: pd.DataFrame, h1_bias: str) -> dict:
        """Find execution entry on M5."""
        if len(df) < 30:
            return {}

        df = add_all_indicators(df)

        sweep = self.sweep_detector.detect(df)
        if not sweep.detected:
            return {"sweep": None, "bos": None, "entry": None}

        # Sweep direction must align with H1 bias
        sweep_aligned = (
            (h1_bias == "bullish" and sweep.direction == "bullish") or
            (h1_bias == "bearish" and sweep.direction == "bearish")
        )

        if not sweep_aligned:
            logger.debug(
                f"M5 sweep direction ({sweep.direction}) conflicts with H1 bias ({h1_bias})"
            )
            return {"sweep": sweep, "bos": None, "entry": None}

        bos = self.bos_detector.detect(df, sweep)
        if not bos.detected:
            return {"sweep": sweep, "bos": None, "entry": None}

        entry = self.entry_finder.find_entry(df, sweep, bos)

        return {
            "sweep": sweep,
            "bos": bos,
            "entry": entry if entry.valid else None,
        }

    def _compute_alignment_score(self, result: MTFAnalysis) -> float:
        """Compute a 0-1 alignment score."""
        score = 0.0

        if result.h1_bias != "neutral":
            score += 0.2

        if result.h1_structure == result.h1_bias:
            score += 0.1

        if result.m15_aligned:
            score += 0.2

        if result.m15_sweep is not None:
            score += 0.1

        if result.m15_bos is not None:
            score += 0.1

        if result.m5_sweep is not None:
            score += 0.1

        if result.m5_bos is not None:
            score += 0.1

        if result.m5_entry is not None:
            score += 0.1

        return round(min(score, 1.0), 3)

    def _is_tradeable(self, result: MTFAnalysis) -> bool:
        """Determine if this setup is worth trading."""
        return (
            result.h1_bias != "neutral"
            and result.m15_aligned
            and result.m5_sweep is not None
            and result.m5_bos is not None
            and result.m5_entry is not None
            and result.m5_entry.valid
            and result.alignment_score >= 0.6
        )

    def _rate_setup(self, result: MTFAnalysis) -> str:
        """Rate setup quality."""
        score = result.alignment_score
        if score >= 0.85:
            return "excellent"
        elif score >= 0.70:
            return "good"
        elif score >= 0.55:
            return "fair"
        else:
            return "poor"
