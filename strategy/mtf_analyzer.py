from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import settings
from core.enums import Bias, Direction, Market, SignalType
from core.models import MarketContext, TradeSignal
from data.candle_manager import CandleManager
from strategy.liquidity import LiquidityAnalyzer
from strategy.pullback import PullbackDetector
from strategy.structure import StructureAnalyzer

logger = logging.getLogger(__name__)


class MTFAnalyzer:
    """
    Multi-Timeframe Analyzer orchestrating:
      H1  -> Market bias
      M15 -> Trend structure + BOS detection
      M5  -> Execution-level pullback entries
    """

    def __init__(self, candle_mgr: CandleManager) -> None:
        self._cm = candle_mgr
        self._structure = StructureAnalyzer()
        self._liquidity = LiquidityAnalyzer()
        self._pullback = PullbackDetector()

    async def analyze(self, symbol: str, market: Market) -> Optional[TradeSignal]:
        df_h1 = await self._cm.refresh(symbol, settings.htf_timeframe)
        df_m15 = await self._cm.refresh(symbol, settings.mtf_timeframe)
        df_m5 = await self._cm.refresh(symbol, settings.ltf_timeframe)

        if df_h1.empty or df_m15.empty or df_m5.empty:
            return None

        ctx = self._build_context(symbol, market, df_h1, df_m15, df_m5)

        if ctx.h1_bias == Bias.NEUTRAL:
            logger.debug("%s: H1 bias neutral — skipping", symbol)
            return None

        signal = self._check_entry(ctx, df_h1, df_m15, df_m5)
        return signal

    def _build_context(
        self,
        symbol: str,
        market: Market,
        df_h1: pd.DataFrame,
        df_m15: pd.DataFrame,
        df_m5: pd.DataFrame,
    ) -> MarketContext:
        h1_bias = self._structure.determine_bias(df_h1)
        m15_bos = self._structure.detect_bos(df_m15)
        liquidity_zones = self._liquidity.detect_liquidity_zones(df_m15)

        atr_h1 = float(df_h1["atr"].iloc[-1]) if "atr" in df_h1.columns and not np.isnan(df_h1["atr"].iloc[-1]) else 0.0
        atr_m15 = float(df_m15["atr"].iloc[-1]) if "atr" in df_m15.columns and not np.isnan(df_m15["atr"].iloc[-1]) else 0.0
        atr_m5 = float(df_m5["atr"].iloc[-1]) if "atr" in df_m5.columns and not np.isnan(df_m5["atr"].iloc[-1]) else 0.0

        swing_highs = self._liquidity.find_swing_highs(df_m15)
        swing_lows = self._liquidity.find_swing_lows(df_m15)

        return MarketContext(
            symbol=symbol,
            market=market,
            h1_bias=h1_bias,
            m15_structure=m15_bos,
            atr_h1=atr_h1,
            atr_m15=atr_m15,
            atr_m5=atr_m5,
            current_price=float(df_m5["close"].iloc[-1]),
            liquidity_zones=liquidity_zones,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
        )

    def _check_entry(
        self,
        ctx: MarketContext,
        df_h1: pd.DataFrame,
        df_m15: pd.DataFrame,
        df_m5: pd.DataFrame,
    ) -> Optional[TradeSignal]:
        swept_zones = self._liquidity.detect_sweep(df_m5, ctx.liquidity_zones)
        if swept_zones:
            signal = self._try_liquidity_sweep_entry(ctx, df_m5, swept_zones)
            if signal:
                return signal

        if ctx.m15_structure is not None:
            bos = ctx.m15_structure
            if (ctx.h1_bias == Bias.BULLISH and bos.direction == Direction.LONG) or \
               (ctx.h1_bias == Bias.BEARISH and bos.direction == Direction.SHORT):
                signal = self._try_pullback_entry(ctx, df_m5, bos)
                if signal:
                    return signal

                signal = self._try_bos_entry(ctx, df_m5, bos)
                if signal:
                    return signal

        return None

    def _try_liquidity_sweep_entry(
        self,
        ctx: MarketContext,
        df_m5: pd.DataFrame,
        swept_zones: list,
    ) -> Optional[TradeSignal]:
        for zone in swept_zones:
            last = df_m5.iloc[-1]

            if zone.price_level < ctx.current_price and ctx.h1_bias == Bias.BULLISH:
                direction = Direction.LONG
            elif zone.price_level > ctx.current_price and ctx.h1_bias == Bias.BEARISH:
                direction = Direction.SHORT
            else:
                continue

            entry = ctx.current_price
            atr = ctx.atr_m5 if ctx.atr_m5 > 0 else ctx.atr_m15
            if atr <= 0:
                continue

            sl_distance = atr * settings.atr_sl_multiplier

            if direction == Direction.LONG:
                sl = entry - sl_distance
                risk = entry - sl
                tp1 = entry + risk * settings.tp1_ratio
                tp2 = entry + risk * settings.tp2_ratio
                tp3 = entry + risk * settings.tp3_ratio
            else:
                sl = entry + sl_distance
                risk = sl - entry
                tp1 = entry - risk * settings.tp1_ratio
                tp2 = entry - risk * settings.tp2_ratio
                tp3 = entry - risk * settings.tp3_ratio

            rr = abs(tp2 - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0
            if rr < settings.min_rr_ratio:
                continue

            return self._build_signal(
                ctx, direction, SignalType.LIQUIDITY_SWEEP,
                entry, sl, tp1, tp2, tp3, rr, df_m5,
            )
        return None

    def _try_pullback_entry(
        self,
        ctx: MarketContext,
        df_m5: pd.DataFrame,
        bos: object,
    ) -> Optional[TradeSignal]:
        swing_low = ctx.swing_lows[-1].price if ctx.swing_lows else 0.0
        swing_high = ctx.swing_highs[-1].price if ctx.swing_highs else 0.0

        if swing_low == 0 or swing_high == 0:
            return None

        pullback = self._pullback.detect(df_m5, bos, swing_low, swing_high)
        if pullback is None:
            return None

        direction = pullback["direction"]
        entry = pullback["entry_price"]
        atr = ctx.atr_m5 if ctx.atr_m5 > 0 else ctx.atr_m15

        struct_sl = swing_low if direction == Direction.LONG else swing_high
        atr_sl_dist = atr * settings.atr_sl_multiplier

        if direction == Direction.LONG:
            sl = min(entry - atr_sl_dist, struct_sl - atr * 0.2)
            risk = entry - sl
        else:
            sl = max(entry + atr_sl_dist, struct_sl + atr * 0.2)
            risk = sl - entry

        if risk <= 0:
            return None

        if direction == Direction.LONG:
            tp1 = entry + risk * settings.tp1_ratio
            tp2 = entry + risk * settings.tp2_ratio
            tp3 = entry + risk * settings.tp3_ratio
        else:
            tp1 = entry - risk * settings.tp1_ratio
            tp2 = entry - risk * settings.tp2_ratio
            tp3 = entry - risk * settings.tp3_ratio

        rr = settings.tp2_ratio
        if rr < settings.min_rr_ratio:
            return None

        return self._build_signal(
            ctx, direction, SignalType.PULLBACK_ENTRY,
            entry, sl, tp1, tp2, tp3, rr, df_m5,
        )

    def _try_bos_entry(
        self,
        ctx: MarketContext,
        df_m5: pd.DataFrame,
        bos: object,
    ) -> Optional[TradeSignal]:
        """Direct BOS entry as fallback when no pullback is found yet."""
        direction = bos.direction
        entry = ctx.current_price
        atr = ctx.atr_m5 if ctx.atr_m5 > 0 else ctx.atr_m15
        if atr <= 0:
            return None

        sl_distance = atr * settings.atr_sl_multiplier

        if direction == Direction.LONG:
            sl = entry - sl_distance
            risk = entry - sl
            tp1 = entry + risk * settings.tp1_ratio
            tp2 = entry + risk * settings.tp2_ratio
            tp3 = entry + risk * settings.tp3_ratio
        else:
            sl = entry + sl_distance
            risk = sl - entry
            tp1 = entry - risk * settings.tp1_ratio
            tp2 = entry - risk * settings.tp2_ratio
            tp3 = entry - risk * settings.tp3_ratio

        rr = settings.tp2_ratio

        return self._build_signal(
            ctx, direction, SignalType.BREAK_OF_STRUCTURE,
            entry, sl, tp1, tp2, tp3, rr, df_m5,
        )

    @staticmethod
    def _build_signal(
        ctx: MarketContext,
        direction: Direction,
        signal_type: SignalType,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float,
        rr: float,
        df_m5: pd.DataFrame,
    ) -> TradeSignal:
        last = df_m5.iloc[-1]
        features = {
            "atr_m5": ctx.atr_m5,
            "atr_m15": ctx.atr_m15,
            "atr_h1": ctx.atr_h1,
            "rsi": float(last.get("rsi", 50)) if not np.isnan(last.get("rsi", 50)) else 50.0,
            "volume_ratio": float(last.get("volume_ratio", 1.0)) if "volume_ratio" in last.index and not np.isnan(last.get("volume_ratio", 1.0)) else 1.0,
            "body_ratio": float(last.get("body_ratio", 0.5)) if "body_ratio" in last.index and not np.isnan(last.get("body_ratio", 0.5)) else 0.5,
            "ema_spread": float(last.get("ema_20", 0) - last.get("ema_50", 0)) if "ema_20" in last.index else 0.0,
            "bias_bullish": 1.0 if ctx.h1_bias == Bias.BULLISH else 0.0,
            "bias_bearish": 1.0 if ctx.h1_bias == Bias.BEARISH else 0.0,
            "signal_liquidity": 1.0 if signal_type == SignalType.LIQUIDITY_SWEEP else 0.0,
            "signal_bos": 1.0 if signal_type == SignalType.BREAK_OF_STRUCTURE else 0.0,
            "signal_pullback": 1.0 if signal_type == SignalType.PULLBACK_ENTRY else 0.0,
            "risk_reward": rr,
            "num_liquidity_zones": float(len(ctx.liquidity_zones)),
        }

        return TradeSignal(
            symbol=ctx.symbol,
            market=ctx.market,
            direction=direction,
            signal_type=signal_type,
            entry_price=entry,
            stop_loss=sl,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            risk_reward=rr,
            context=ctx,
            features=features,
        )
