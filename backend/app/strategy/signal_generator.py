"""
Signal Generator

Orchestrates the full strategy pipeline:
1. Detect Liquidity Sweep
2. Confirm Break of Structure
3. Build Pullback Entry Signal
4. Score with AI Classifier
"""

import pandas as pd
import numpy as np
import logging
from typing import Optional
from datetime import datetime, timezone

from app.strategy.liquidity_sweep import detect_liquidity_sweep, get_sweep_bias, calculate_atr
from app.strategy.break_of_structure import detect_break_of_structure, get_bos_entry_zone
from app.strategy.pullback_entry import build_entry_signal, EntrySignal

logger = logging.getLogger(__name__)


class SignalGenerator:
    def __init__(
        self,
        symbol: str,
        market: str,
        timeframe: str,
        tp1_ratio: float = 1.5,
        tp2_ratio: float = 2.5,
        tp3_ratio: float = 4.0,
    ):
        self.symbol = symbol
        self.market = market
        self.timeframe = timeframe
        self.tp1_ratio = tp1_ratio
        self.tp2_ratio = tp2_ratio
        self.tp3_ratio = tp3_ratio

    def generate(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Run the full signal pipeline on a given OHLCV DataFrame.

        Returns a signal dict or None if no setup found.
        """
        if df is None or len(df) < 50:
            logger.debug(f"[{self.symbol}] Insufficient data ({len(df) if df is not None else 0} bars)")
            return None

        # Ensure required columns
        required = ["open", "high", "low", "close", "volume"]
        if not all(c in df.columns for c in required):
            logger.warning(f"[{self.symbol}] Missing columns in DataFrame")
            return None

        df = df.copy().reset_index(drop=True)

        # Step 1: ATR
        atr_series = calculate_atr(df)
        atr = float(atr_series.iloc[-1])
        if np.isnan(atr) or atr == 0:
            return None

        # Step 2: Liquidity Sweep
        sweep = detect_liquidity_sweep(df)
        if sweep is None or not sweep.confirmed:
            logger.debug(f"[{self.symbol}] No liquidity sweep detected")
            return None

        bias = get_sweep_bias(sweep)
        logger.info(f"[{self.symbol}] Sweep detected: {sweep.direction} @ {sweep.swept_level:.5f}")

        # Step 3: Break of Structure
        bos = detect_break_of_structure(df, bias)
        if bos is None or not bos.confirmed:
            logger.debug(f"[{self.symbol}] No BOS confirmed after sweep")
            return None

        logger.info(f"[{self.symbol}] BOS confirmed: {bos.direction} @ {bos.broken_level:.5f}")

        # Step 4: Pullback Entry
        entry = build_entry_signal(
            df, bos, bias, atr,
            tp1_ratio=self.tp1_ratio,
            tp2_ratio=self.tp2_ratio,
            tp3_ratio=self.tp3_ratio,
        )
        if entry is None:
            logger.debug(f"[{self.symbol}] No valid pullback entry found")
            return None

        logger.info(f"[{self.symbol}] Entry signal built: {entry.direction} @ {entry.entry_price:.5f}")

        # Determine session
        now = datetime.now(timezone.utc)
        hour = now.hour
        if 7 <= hour < 12:
            session = "LONDON"
        elif 12 <= hour < 17:
            session = "LONDON_NY_OVERLAP"
        elif 17 <= hour < 21:
            session = "NEW_YORK"
        else:
            session = "ASIA"

        return {
            "symbol": self.symbol,
            "market": self.market,
            "timeframe": self.timeframe,
            "direction": entry.direction,
            "entry_zone_low": round(entry.entry_zone_low, 5),
            "entry_zone_high": round(entry.entry_zone_high, 5),
            "entry_price": round(entry.entry_price, 5),
            "stop_loss": round(entry.stop_loss, 5),
            "tp1": round(entry.tp1, 5),
            "tp2": round(entry.tp2, 5),
            "tp3": round(entry.tp3, 5),
            "atr_value": round(atr, 5),
            "liquidity_sweep_detected": True,
            "bos_detected": True,
            "pullback_confirmed": True,
            "sweep_level": round(sweep.swept_level, 5),
            "bos_level": round(bos.broken_level, 5),
            "setup_quality": entry.setup_quality,
            "rsi": entry.rsi_value,
            "fvg_detected": entry.fvg_detected,
            "order_block_level": entry.order_block_level,
            "session": session,
            "market_structure": f"{sweep.direction} -> {bos.direction}",
            "timestamp": now.isoformat(),
        }
