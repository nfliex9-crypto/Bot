"""
Smart Money Concepts (SMC) Strategy Engine.

Core logic:
1. H1  — Determine market bias (bullish/bearish/neutral)
2. M15 — Identify trend structure and break-of-structure
3. M5  — Detect liquidity sweeps and pullback entries

Signal generation flow:
  Liquidity Sweep → Break of Structure → Pullback to OB/FVG → Entry
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from config.settings import StrategyConfig
from core.logger import get_logger
from core.models import (
    Direction, LiquidityZone, MarketBias, SignalStrength,
    StructureBreak, StructureType, SwingPoint, TradeSignal,
)
from strategy.indicators import atr, ema, order_block_detector, rsi, vwap
from strategy.liquidity import LiquidityAnalyzer
from strategy.structure import StructureAnalyzer

logger = get_logger("strategy.smc")


class SMCStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.structure = StructureAnalyzer(lookback=config.structure_lookback)
        self.liquidity = LiquidityAnalyzer(lookback=config.liquidity_lookback)

    async def analyze(
        self,
        h1_data: pd.DataFrame,
        m15_data: pd.DataFrame,
        m5_data: pd.DataFrame,
        symbol: str,
    ) -> Optional[TradeSignal]:
        """
        Multi-timeframe analysis pipeline.
        Returns a TradeSignal if all conditions align, else None.
        """
        if h1_data.empty or m15_data.empty or m5_data.empty:
            return None

        htf_bias, htf_swings, htf_breaks = self.structure.get_trend_direction(h1_data)
        if htf_bias == MarketBias.NEUTRAL:
            logger.debug(f"{symbol}: H1 bias neutral — skipping")
            return None

        mtf_bias, mtf_swings, mtf_breaks = self.structure.get_trend_direction(m15_data)
        if not self._bias_aligned(htf_bias, mtf_bias):
            logger.debug(f"{symbol}: M15 not aligned with H1 — skipping")
            return None

        confirmed_bos = [b for b in mtf_breaks if b.confirmed and
                         b.break_type == StructureType.BREAK_OF_STRUCTURE]
        if not confirmed_bos:
            logger.debug(f"{symbol}: No confirmed BOS on M15")
            return None

        latest_bos = confirmed_bos[-1]
        if not self._bos_matches_bias(latest_bos, htf_bias):
            return None

        ltf_swings = self.structure.find_swing_points(m5_data, left=3, right=3)
        liq_zones = self.liquidity.find_liquidity_zones(m5_data, ltf_swings)
        sweeps = self.liquidity.detect_sweep(m5_data, liq_zones)

        valid_sweeps = self._filter_sweeps_by_bias(sweeps, htf_bias)
        if not valid_sweeps:
            logger.debug(f"{symbol}: No aligned liquidity sweep on M5")
            return None

        entry_zone = self._find_pullback_entry(m5_data, htf_bias, ltf_swings)
        if entry_zone is None:
            logger.debug(f"{symbol}: No pullback entry zone found")
            return None

        entry_price, stop_loss = entry_zone
        current_atr = self._get_atr(m5_data)

        direction = Direction.LONG if htf_bias == MarketBias.BULLISH else Direction.SHORT
        tp1, tp2, tp3 = self._calculate_targets(entry_price, stop_loss, direction)

        risk_reward = abs(tp1 - entry_price) / abs(entry_price - stop_loss) if abs(entry_price - stop_loss) > 0 else 0

        confidence = self._calculate_base_confidence(
            htf_bias, mtf_bias, valid_sweeps, confirmed_bos, ltf_swings, m5_data
        )

        strength = SignalStrength.STRONG if confidence >= 0.75 else (
            SignalStrength.MODERATE if confidence >= 0.6 else SignalStrength.WEAK
        )

        signal = TradeSignal(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1=tp1, tp2=tp2, tp3=tp3,
            confidence=confidence,
            strength=strength,
            market_bias=htf_bias,
            timeframe=self.config.ltf_timeframe,
            reason=self._build_reason(htf_bias, latest_bos, valid_sweeps[0]),
            risk_reward=risk_reward,
            metadata={
                "htf_bias": htf_bias.value,
                "mtf_bias": mtf_bias.value,
                "bos_count": len(confirmed_bos),
                "sweep_count": len(valid_sweeps),
                "atr": float(current_atr) if not np.isnan(current_atr) else 0,
            },
        )

        logger.info(
            f"Signal generated: {symbol} {direction.value} @ {entry_price:.5f} "
            f"SL={stop_loss:.5f} TP1={tp1:.5f} conf={confidence:.2f}"
        )
        return signal

    def _bias_aligned(self, htf: MarketBias, mtf: MarketBias) -> bool:
        return htf == mtf or mtf == MarketBias.NEUTRAL

    def _bos_matches_bias(self, bos: StructureBreak, bias: MarketBias) -> bool:
        if bias == MarketBias.BULLISH:
            return bos.direction == Direction.LONG
        if bias == MarketBias.BEARISH:
            return bos.direction == Direction.SHORT
        return False

    def _filter_sweeps_by_bias(self, sweeps, bias: MarketBias):
        filtered = []
        for zone, sweep_dir in sweeps:
            if bias == MarketBias.BULLISH and sweep_dir == "bullish_sweep":
                filtered.append((zone, sweep_dir))
            elif bias == MarketBias.BEARISH and sweep_dir == "bearish_sweep":
                filtered.append((zone, sweep_dir))
        return filtered

    def _find_pullback_entry(
        self, df: pd.DataFrame, bias: MarketBias, swings: List[SwingPoint]
    ) -> Optional[Tuple[float, float]]:
        """
        Look for a pullback into an order block or FVG for entry,
        with ATR-based or structure-based stop loss.
        """
        if len(df) < 10:
            return None

        obs = order_block_detector(df, lookback=15)
        current_price = float(df.iloc[-1]["close"])
        current_atr = self._get_atr(df)

        if bias == MarketBias.BULLISH:
            bullish_obs = [ob for ob in obs if ob["type"] == "bullish_ob"]
            for ob in reversed(bullish_obs):
                if ob["low"] <= current_price <= ob["high"] * 1.002:
                    entry = current_price
                    sl = entry - current_atr * self.config.atr_multiplier
                    recent_lows = [s.price for s in swings if not s.is_high][-3:]
                    if recent_lows:
                        struct_sl = min(recent_lows) - current_atr * 0.3
                        sl = max(sl, struct_sl)
                    return entry, sl

            recent_lows = [s for s in swings if not s.is_high]
            if recent_lows:
                last_low = recent_lows[-1]
                if current_price <= last_low.price * 1.003:
                    entry = current_price
                    sl = entry - current_atr * self.config.atr_multiplier
                    return entry, sl

        elif bias == MarketBias.BEARISH:
            bearish_obs = [ob for ob in obs if ob["type"] == "bearish_ob"]
            for ob in reversed(bearish_obs):
                if ob["low"] * 0.998 <= current_price <= ob["high"]:
                    entry = current_price
                    sl = entry + current_atr * self.config.atr_multiplier
                    recent_highs = [s.price for s in swings if s.is_high][-3:]
                    if recent_highs:
                        struct_sl = max(recent_highs) + current_atr * 0.3
                        sl = min(sl, struct_sl)
                    return entry, sl

            recent_highs = [s for s in swings if s.is_high]
            if recent_highs:
                last_high = recent_highs[-1]
                if current_price >= last_high.price * 0.997:
                    entry = current_price
                    sl = entry + current_atr * self.config.atr_multiplier
                    return entry, sl

        return None

    def _get_atr(self, df: pd.DataFrame) -> float:
        atr_series = atr(df, self.config.atr_period)
        val = atr_series.iloc[-1] if not atr_series.empty else 0.0
        return float(val) if not np.isnan(val) else 0.0

    def _calculate_targets(
        self, entry: float, sl: float, direction: Direction
    ) -> Tuple[float, float, float]:
        risk = abs(entry - sl)
        if direction == Direction.LONG:
            tp1 = entry + risk * self.config.tp1_ratio
            tp2 = entry + risk * self.config.tp2_ratio
            tp3 = entry + risk * self.config.tp3_ratio
        else:
            tp1 = entry - risk * self.config.tp1_ratio
            tp2 = entry - risk * self.config.tp2_ratio
            tp3 = entry - risk * self.config.tp3_ratio
        return tp1, tp2, tp3

    def _calculate_base_confidence(
        self, htf_bias, mtf_bias, sweeps, bos_list, swings, df
    ) -> float:
        score = 0.0
        score += 0.20 if htf_bias == mtf_bias else 0.10
        score += min(len(sweeps) * 0.15, 0.25)
        score += min(len(bos_list) * 0.10, 0.20)

        rsi_val = rsi(df).iloc[-1] if len(df) > 14 else 50
        if not np.isnan(rsi_val):
            if htf_bias == MarketBias.BULLISH and rsi_val < 40:
                score += 0.10
            elif htf_bias == MarketBias.BEARISH and rsi_val > 60:
                score += 0.10

        if len(swings) >= 4:
            score += 0.10

        ema_20 = ema(df["close"], 20)
        if not ema_20.empty and not np.isnan(ema_20.iloc[-1]):
            price = df.iloc[-1]["close"]
            if htf_bias == MarketBias.BULLISH and price > ema_20.iloc[-1]:
                score += 0.05
            elif htf_bias == MarketBias.BEARISH and price < ema_20.iloc[-1]:
                score += 0.05

        return min(score, 1.0)

    def _build_reason(self, bias, bos, sweep) -> str:
        zone, sweep_dir = sweep
        return (
            f"{bias.value.upper()} bias | BOS {bos.direction.value} @ {bos.price:.5f} | "
            f"{sweep_dir} @ {zone.price_level:.5f}"
        )
