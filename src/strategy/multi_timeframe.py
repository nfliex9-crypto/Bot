"""
Multi-Timeframe Analysis Engine.

H1  → Market bias  (bullish / bearish / ranging)
M15 → Trend structure (BOS/CHoCH confirmation + order blocks)
M5  → Execution entry (liquidity sweep + pullback)

All three timeframes must align for a valid trade signal.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
import pandas as pd
from loguru import logger

from src.strategy.break_of_structure import BreakOfStructureDetector, BOSResult
from src.strategy.liquidity_sweep import LiquiditySweepDetector, SweepResult
from src.strategy.pullback_entry import PullbackEntryDetector, PullbackResult
from src.strategy.indicators import calculate_atr, calculate_ema, calculate_rsi
from config.settings import settings


@dataclass
class TimeframeAnalysis:
    timeframe: str
    trend: str                   # "bullish" | "bearish" | "ranging"
    bos: BOSResult
    sweep: SweepResult
    pullback: PullbackResult
    atr: float
    ema_fast: float
    ema_slow: float
    rsi: float
    current_price: float
    raw_df: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass
class MTFSignal:
    """
    Consolidated multi-timeframe signal ready for AI scoring and execution.
    """
    symbol: str
    market: str                  # "forex" | "crypto"
    direction: Optional[str]     # "bullish" | "bearish" | None
    valid: bool
    confidence: float            # Pre-AI composite score 0–1

    htf: TimeframeAnalysis       # H1
    mtf: TimeframeAnalysis       # M15
    ltf: TimeframeAnalysis       # M5

    entry_price: Optional[float]
    stop_loss: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    atr: Optional[float]
    risk_reward: Optional[float]

    rejection_reason: Optional[str] = None


class MultiTimeframeAnalyzer:
    """
    Orchestrates multi-timeframe analysis across H1, M15, M5.
    Returns structured MTFSignal for each symbol.
    """

    def __init__(self):
        self.bos_detector = BreakOfStructureDetector(lookback=settings.swing_lookback)
        self.sweep_detector = LiquiditySweepDetector(lookback=settings.swing_lookback)
        self.pullback_detector = PullbackEntryDetector()

    async def analyse(
        self,
        symbol: str,
        market: str,
        htf_df: pd.DataFrame,
        mtf_df: pd.DataFrame,
        ltf_df: pd.DataFrame,
    ) -> MTFSignal:
        """
        Run full MTF analysis on a symbol.
        Returns an MTFSignal with all analysis results.
        """
        logger.debug(f"[MTF] Analysing {symbol} | H1={len(htf_df)} M15={len(mtf_df)} M5={len(ltf_df)}")

        if any(df.empty or len(df) < 30 for df in [htf_df, mtf_df, ltf_df]):
            return self._reject(symbol, market, "Insufficient data for analysis")

        # ─── H1: Market Bias ─────────────────────────────────────────────────
        htf = self._analyse_timeframe(htf_df, "H1")

        # ─── M15: Trend Structure ────────────────────────────────────────────
        mtf = self._analyse_timeframe(mtf_df, "M15")

        # ─── M5: Execution ───────────────────────────────────────────────────
        ltf = self._analyse_timeframe(ltf_df, "M5")

        # ─── Alignment Check ─────────────────────────────────────────────────
        direction = self._check_alignment(htf, mtf, ltf)
        if direction is None:
            return self._reject(
                symbol, market, f"MTF misaligned H1={htf.trend} M15={mtf.trend} M5={ltf.trend}"
            )

        # ─── Entry Levels ─────────────────────────────────────────────────────
        entry_data = self._calculate_entry_levels(direction, ltf, mtf)
        if not entry_data:
            return self._reject(symbol, market, "Could not determine entry levels")

        entry, sl, tp1, tp2, tp3, atr = entry_data
        rr = round((tp1 - entry) / (entry - sl), 2) if direction == "bullish" else round((entry - tp1) / (sl - entry), 2)

        # ─── Composite Pre-AI Confidence ─────────────────────────────────────
        confidence = self._calculate_composite_confidence(direction, htf, mtf, ltf)

        return MTFSignal(
            symbol=symbol,
            market=market,
            direction=direction,
            valid=True,
            confidence=confidence,
            htf=htf,
            mtf=mtf,
            ltf=ltf,
            entry_price=entry,
            stop_loss=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            atr=atr,
            risk_reward=rr,
        )

    def _analyse_timeframe(self, df: pd.DataFrame, label: str) -> TimeframeAnalysis:
        """Run all indicators and pattern detection on a single timeframe."""
        atr_series = calculate_atr(df, settings.atr_period)
        ema_fast_series = calculate_ema(df["close"], 20)
        ema_slow_series = calculate_ema(df["close"], 50)
        rsi_series = calculate_rsi(df["close"], 14)

        bos = self.bos_detector.detect(df)
        sweep = self.sweep_detector.detect(df)

        # Determine impulse for pullback: use last BOS level if available
        current_price = float(df["close"].iloc[-1])
        impulse_start = float(df["low"].iloc[-20:].min()) if bos.trend == "bullish" else float(df["high"].iloc[-20:].max())
        impulse_end = float(df["high"].iloc[-5:].max()) if bos.trend == "bullish" else float(df["low"].iloc[-5:].min())

        pullback = self.pullback_detector.detect(df, bos.trend or "bullish", impulse_start, impulse_end)

        return TimeframeAnalysis(
            timeframe=label,
            trend=bos.trend or "ranging",
            bos=bos,
            sweep=sweep,
            pullback=pullback,
            atr=float(atr_series.iloc[-1]) if not atr_series.empty else 0.0,
            ema_fast=float(ema_fast_series.iloc[-1]) if not ema_fast_series.empty else 0.0,
            ema_slow=float(ema_slow_series.iloc[-1]) if not ema_slow_series.empty else 0.0,
            rsi=float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0,
            current_price=current_price,
            raw_df=df,
        )

    def _check_alignment(
        self, htf: TimeframeAnalysis, mtf: TimeframeAnalysis, ltf: TimeframeAnalysis
    ) -> Optional[str]:
        """
        All three timeframes must agree on direction.
        HTF sets the bias; MTF confirms structure; LTF provides entry.
        """
        if htf.trend == "ranging":
            return None

        # Both MTF and LTF must not oppose the HTF bias
        for tf in [mtf, ltf]:
            if tf.trend not in (htf.trend, "ranging"):
                return None

        # At least one of MTF/LTF must confirm the same direction
        confirmations = sum(1 for tf in [mtf, ltf] if tf.trend == htf.trend)
        if confirmations < 1:
            return None

        return htf.trend

    def _calculate_entry_levels(
        self, direction: str, ltf: TimeframeAnalysis, mtf: TimeframeAnalysis
    ) -> Optional[Tuple[float, float, float, float, float, float]]:
        """
        Calculate entry, SL and TPs based on ATR and structure.
        Returns (entry, sl, tp1, tp2, tp3, atr) or None.
        """
        atr = ltf.atr
        if atr == 0:
            atr = mtf.atr
        if atr == 0:
            return None

        current = ltf.current_price

        # Use pullback-suggested entry if available, else current price
        if ltf.pullback.valid and ltf.pullback.suggested_entry:
            entry = ltf.pullback.suggested_entry
        else:
            entry = current

        # Structure-based stop: below last swing low (bull) or above last swing high (bear)
        last_high, last_low = self.bos_detector.get_last_structure_levels(ltf.raw_df)

        if direction == "bullish":
            # SL: ATR below the sweep low or swing low
            atr_sl = entry - atr * settings.atr_multiplier
            structure_sl = (ltf.sweep.sweep_low or last_low or atr_sl) - atr * 0.5
            sl = min(atr_sl, structure_sl) if structure_sl else atr_sl
            risk = entry - sl
            if risk <= 0:
                return None
            tp1 = entry + risk * settings.tp1_r
            tp2 = entry + risk * settings.tp2_r
            tp3 = entry + risk * settings.tp3_r
        else:
            atr_sl = entry + atr * settings.atr_multiplier
            structure_sl = (ltf.sweep.sweep_high or last_high or atr_sl) + atr * 0.5
            sl = max(atr_sl, structure_sl) if structure_sl else atr_sl
            risk = sl - entry
            if risk <= 0:
                return None
            tp1 = entry - risk * settings.tp1_r
            tp2 = entry - risk * settings.tp2_r
            tp3 = entry - risk * settings.tp3_r

        return entry, sl, tp1, tp2, tp3, atr

    def _calculate_composite_confidence(
        self,
        direction: str,
        htf: TimeframeAnalysis,
        mtf: TimeframeAnalysis,
        ltf: TimeframeAnalysis,
    ) -> float:
        """
        Calculate a composite confidence score (0–1) from structural factors.
        This feeds into the AI classifier as a baseline.
        """
        score = 0.0
        factors = 0

        # HTF BOS confirmation
        if htf.bos.detected:
            score += 0.15
        factors += 1

        # MTF BOS/CHoCH
        if mtf.bos.detected:
            score += 0.20
        factors += 1

        # LTF sweep
        if ltf.sweep.detected and ltf.sweep.direction == direction:
            score += 0.25
        factors += 1

        # LTF pullback
        if ltf.pullback.valid:
            bonus = {"order_block": 0.20, "fvg": 0.15, "fibonacci": 0.10}
            score += bonus.get(ltf.pullback.entry_type or "fibonacci", 0.10)
        factors += 1

        # RSI alignment
        if direction == "bullish" and 30 <= ltf.rsi <= 60:
            score += 0.10
        elif direction == "bearish" and 40 <= ltf.rsi <= 70:
            score += 0.10
        factors += 1

        # EMA alignment
        if direction == "bullish" and ltf.ema_fast > ltf.ema_slow:
            score += 0.10
        elif direction == "bearish" and ltf.ema_fast < ltf.ema_slow:
            score += 0.10
        factors += 1

        return round(min(score, 1.0), 4)

    def _reject(self, symbol: str, market: str, reason: str) -> MTFSignal:
        empty_tf = TimeframeAnalysis(
            timeframe="", trend="ranging",
            bos=BOSResult(False, None, None, None, None),
            sweep=SweepResult(False, None, None, None, None, None, 0.0),
            pullback=PullbackResult(False, None, None, None, None, None, None, None, None),
            atr=0.0, ema_fast=0.0, ema_slow=0.0, rsi=50.0, current_price=0.0,
        )
        return MTFSignal(
            symbol=symbol, market=market, direction=None,
            valid=False, confidence=0.0,
            htf=empty_tf, mtf=empty_tf, ltf=empty_tf,
            entry_price=None, stop_loss=None,
            tp1=None, tp2=None, tp3=None,
            atr=None, risk_reward=None,
            rejection_reason=reason,
        )
