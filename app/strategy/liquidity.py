from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import Settings
from app.domain.models import MarketType, SignalContext, TradeSide, TradeSignal


def _to_frame(candles: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required.difference(candles.columns)
    if missing:
        raise ValueError(f"Missing candle columns: {sorted(missing)}")
    frame = candles.copy()
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    return frame.reset_index(drop=True)


def compute_atr(frame: pd.DataFrame, period: int) -> pd.Series:
    high_low = frame["high"] - frame["low"]
    high_close = (frame["high"] - frame["close"].shift(1)).abs()
    low_close = (frame["low"] - frame["close"].shift(1)).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period, min_periods=period).mean().bfill()


class LiquiditySweepStrategy:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_signal(
        self,
        symbol: str,
        market: MarketType,
        h1_frame: pd.DataFrame,
        m15_frame: pd.DataFrame,
        m5_frame: pd.DataFrame,
    ) -> TradeSignal | None:
        h1 = _to_frame(h1_frame)
        m15 = _to_frame(m15_frame)
        m5 = _to_frame(m5_frame)

        bias, bias_strength = self._determine_h1_bias(h1)
        if bias is None:
            return None

        context = self._analyze_structure(bias, h1, m15, m5)
        if not context.sweep_detected or context.bos_level is None or context.pullback_level is None:
            return None

        signal = self._build_signal(symbol, market, bias, m5, context)
        if signal is None:
            return None
        return signal

    def _determine_h1_bias(self, h1: pd.DataFrame) -> tuple[TradeSide | None, float]:
        h1 = h1.copy()
        h1["ema_fast"] = h1["close"].ewm(span=20, adjust=False).mean()
        h1["ema_slow"] = h1["close"].ewm(span=50, adjust=False).mean()
        atr = compute_atr(h1, self.settings.atr_period).iloc[-1]
        last = h1.iloc[-1]
        recent_high = h1["high"].iloc[-10:-1].max()
        recent_low = h1["low"].iloc[-10:-1].min()
        if np.isnan(atr) or atr == 0:
            return None, 0.0

        bullish = (
            last["close"] > last["ema_fast"] > last["ema_slow"]
            and last["close"] >= recent_high * 0.998
        )
        bearish = (
            last["close"] < last["ema_fast"] < last["ema_slow"]
            and last["close"] <= recent_low * 1.002
        )
        strength = float(abs(last["close"] - last["ema_slow"]) / atr)
        if bullish:
            return TradeSide.BUY, min(strength, 3.0)
        if bearish:
            return TradeSide.SELL, min(strength, 3.0)
        return None, strength

    def _analyze_structure(
        self,
        bias: TradeSide,
        h1: pd.DataFrame,
        m15: pd.DataFrame,
        m5: pd.DataFrame,
    ) -> SignalContext:
        m15_atr = float(compute_atr(m15, self.settings.atr_period).iloc[-1])
        m5_atr = float(compute_atr(m5, self.settings.atr_period).iloc[-1])
        sweep_index, bos_level, sweep_depth = self._find_sweep_and_bos(m15, bias, m15_atr)
        pullback_level, structure_stop, entry_quality = self._locate_pullback(m5, bias, bos_level, m5_atr)

        feature_map = {
            "h1_volatility": float(compute_atr(h1, self.settings.atr_period).iloc[-1] / max(h1["close"].iloc[-1], 1e-9)),
            "m15_sweep_depth": float(sweep_depth),
            "m15_bos_distance": float(abs(m15["close"].iloc[-1] - bos_level) / max(m15_atr, 1e-9)) if bos_level else 0.0,
            "m5_entry_quality": float(entry_quality),
            "atr_ratio": float(m5_atr / max(m5["close"].iloc[-1], 1e-9)),
            "bias_alignment": 1.0,
        }
        rationale: list[str] = [f"H1 bias: {bias.value}"]
        if sweep_index is not None:
            rationale.append("Liquidity sweep confirmed on M15")
        if bos_level is not None:
            rationale.append(f"Break of structure at {bos_level:.5f}")
        if pullback_level is not None:
            rationale.append(f"M5 pullback entry near {pullback_level:.5f}")

        return SignalContext(
            bias=bias,
            sweep_detected=sweep_index is not None,
            bos_level=bos_level,
            pullback_level=pullback_level,
            atr=m5_atr,
            structure_stop=structure_stop,
            feature_map=feature_map,
            rationale=rationale,
        )

    def _find_sweep_and_bos(
        self,
        m15: pd.DataFrame,
        bias: TradeSide,
        atr: float,
    ) -> tuple[int | None, float | None, float]:
        lookback = 20
        if len(m15) < lookback + 8:
            return None, None, 0.0

        for idx in range(len(m15) - 6, lookback - 1, -1):
            window = m15.iloc[idx - lookback:idx]
            candle = m15.iloc[idx]
            if bias == TradeSide.BUY:
                prior_low = float(window["low"].min())
                if candle["low"] < prior_low and candle["close"] > prior_low:
                    reference_high = float(m15["high"].iloc[max(idx - 5, 0):idx + 1].max())
                    if float(m15["close"].iloc[idx + 1:].max()) > reference_high:
                        sweep_depth = (prior_low - candle["low"]) / max(atr, 1e-9)
                        return idx, reference_high, max(sweep_depth, 0.0)
            else:
                prior_high = float(window["high"].max())
                if candle["high"] > prior_high and candle["close"] < prior_high:
                    reference_low = float(m15["low"].iloc[max(idx - 5, 0):idx + 1].min())
                    if float(m15["close"].iloc[idx + 1:].min()) < reference_low:
                        sweep_depth = (candle["high"] - prior_high) / max(atr, 1e-9)
                        return idx, reference_low, max(sweep_depth, 0.0)

        return None, None, 0.0

    def _locate_pullback(
        self,
        m5: pd.DataFrame,
        bias: TradeSide,
        bos_level: float | None,
        atr: float,
    ) -> tuple[float | None, float | None, float]:
        if bos_level is None or len(m5) < 10:
            return None, None, 0.0

        recent = m5.iloc[-8:].copy()
        tolerance = atr * 0.45
        last = recent.iloc[-1]
        if bias == TradeSide.BUY:
            touched = recent[(recent["low"] <= bos_level + tolerance) & (recent["close"] >= bos_level)]
            if touched.empty or last["close"] <= last["open"]:
                return None, None, 0.0
            pullback_level = float(touched["low"].iloc[-1])
            structure_stop = float(min(recent["low"].min(), pullback_level - atr * self.settings.structure_stop_buffer_atr))
            quality = max(0.0, 1.0 - abs(last["close"] - bos_level) / max(atr * 1.5, 1e-9))
            return pullback_level, structure_stop, float(min(quality, 1.0))

        touched = recent[(recent["high"] >= bos_level - tolerance) & (recent["close"] <= bos_level)]
        if touched.empty or last["close"] >= last["open"]:
            return None, None, 0.0
        pullback_level = float(touched["high"].iloc[-1])
        structure_stop = float(max(recent["high"].max(), pullback_level + atr * self.settings.structure_stop_buffer_atr))
        quality = max(0.0, 1.0 - abs(last["close"] - bos_level) / max(atr * 1.5, 1e-9))
        return pullback_level, structure_stop, float(min(quality, 1.0))

    def _build_signal(
        self,
        symbol: str,
        market: MarketType,
        bias: TradeSide,
        m5: pd.DataFrame,
        context: SignalContext,
    ) -> TradeSignal | None:
        last = m5.iloc[-1]
        entry = float(last["close"])
        atr_stop = entry - context.atr * 1.2 if bias == TradeSide.BUY else entry + context.atr * 1.2
        structure_stop = context.structure_stop or atr_stop

        if bias == TradeSide.BUY:
            stop_loss = min(atr_stop, structure_stop)
            risk = entry - stop_loss
            if risk <= 0:
                return None
            tp1 = entry + risk
            tp2 = entry + risk * 1.5
            tp3 = entry + risk * 2
        else:
            stop_loss = max(atr_stop, structure_stop)
            risk = stop_loss - entry
            if risk <= 0:
                return None
            tp1 = entry - risk
            tp2 = entry - risk * 1.5
            tp3 = entry - risk * 2

        baseline_confidence = min(
            0.55
            + context.feature_map["m15_sweep_depth"] * 0.08
            + context.feature_map["m5_entry_quality"] * 0.12,
            0.9,
        )
        metadata: dict[str, Any] = {
            "bias": bias.value,
            "atr": context.atr,
            "bos_level": context.bos_level,
            "pullback_level": context.pullback_level,
            "structure_stop": context.structure_stop,
            "feature_map": context.feature_map,
            "rationale": context.rationale,
        }
        return TradeSignal(
            symbol=symbol,
            market=market,
            side=bias,
            entry=entry,
            stop_loss=float(stop_loss),
            take_profit_1=float(tp1),
            take_profit_2=float(tp2),
            take_profit_3=float(tp3),
            confidence=float(baseline_confidence),
            stop_method="atr_structure_hybrid",
            metadata=metadata,
        )
