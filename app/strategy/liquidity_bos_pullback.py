from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.config import Settings
from app.schemas import Signal


@dataclass
class StrategyContext:
    market: str
    symbol: str
    df_h1: pd.DataFrame
    df_m15: pd.DataFrame
    df_m5: pd.DataFrame


class LiquiditySweepBOSPullbackStrategy:
    def __init__(self, settings: Settings):
        self.settings = settings

    @staticmethod
    def _ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> float:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return float(atr.iloc[-1])

    @staticmethod
    def _swing_levels(df: pd.DataFrame, window: int = 3) -> tuple[float, float]:
        highs = df["high"].rolling(window=window, center=True).max()
        lows = df["low"].rolling(window=window, center=True).min()
        swing_high = float(highs.iloc[-window - 1 : -1].max())
        swing_low = float(lows.iloc[-window - 1 : -1].min())
        return swing_high, swing_low

    def _get_bias(self, df_h1: pd.DataFrame) -> str:
        ema_fast = self._ema(df_h1["close"], 20).iloc[-1]
        ema_slow = self._ema(df_h1["close"], 50).iloc[-1]
        close = float(df_h1["close"].iloc[-1])
        if close > ema_fast > ema_slow:
            return "bullish"
        if close < ema_fast < ema_slow:
            return "bearish"
        return "neutral"

    def _liquidity_sweep(self, df: pd.DataFrame) -> Optional[str]:
        if len(df) < 20:
            return None
        prev_high = float(df["high"].iloc[-20:-1].max())
        prev_low = float(df["low"].iloc[-20:-1].min())
        last = df.iloc[-1]
        if float(last["high"]) > prev_high and float(last["close"]) < prev_high:
            return "sell"
        if float(last["low"]) < prev_low and float(last["close"]) > prev_low:
            return "buy"
        return None

    def _bos_direction(self, df_m15: pd.DataFrame) -> Optional[str]:
        if len(df_m15) < 30:
            return None
        recent = df_m15.iloc[-12:]
        prev = df_m15.iloc[-30:-12]
        prev_high = float(prev["high"].max())
        prev_low = float(prev["low"].min())
        close = float(recent["close"].iloc[-1])
        if close > prev_high:
            return "buy"
        if close < prev_low:
            return "sell"
        return None

    def _pullback_entry(self, side: str, df_m5: pd.DataFrame) -> Optional[float]:
        if len(df_m5) < 15:
            return None
        impulse = df_m5.iloc[-15:-5]
        pullback = df_m5.iloc[-5:]
        impulse_high = float(impulse["high"].max())
        impulse_low = float(impulse["low"].min())
        mid = impulse_low + (impulse_high - impulse_low) * 0.5
        close = float(pullback["close"].iloc[-1])

        if side == "buy" and close >= mid:
            return close
        if side == "sell" and close <= mid:
            return close
        return None

    def _stop_loss(self, side: str, entry: float, atr: float, structure_high: float, structure_low: float) -> float:
        atr_sl = entry - atr * self.settings.atr_multiplier if side == "buy" else entry + atr * self.settings.atr_multiplier
        if self.settings.stop_loss_mode == "atr":
            return atr_sl

        if side == "buy":
            return min(atr_sl, structure_low - self.settings.structure_padding)
        return max(atr_sl, structure_high + self.settings.structure_padding)

    def _targets(self, side: str, entry: float, stop: float) -> tuple[float, float, float]:
        risk = abs(entry - stop)
        if side == "buy":
            return (
                entry + risk * self.settings.tp1_r_multiple,
                entry + risk * self.settings.tp2_r_multiple,
                entry + risk * self.settings.tp3_r_multiple,
            )
        return (
            entry - risk * self.settings.tp1_r_multiple,
            entry - risk * self.settings.tp2_r_multiple,
            entry - risk * self.settings.tp3_r_multiple,
        )

    def generate_signal(self, ctx: StrategyContext) -> Optional[Signal]:
        if min(len(ctx.df_h1), len(ctx.df_m15), len(ctx.df_m5)) < 60:
            return None

        bias = self._get_bias(ctx.df_h1)
        if bias == "neutral":
            return None

        sweep_side = self._liquidity_sweep(ctx.df_m15)
        bos_side = self._bos_direction(ctx.df_m15)
        if not sweep_side or not bos_side or sweep_side != bos_side:
            return None

        if (bias == "bullish" and sweep_side != "buy") or (bias == "bearish" and sweep_side != "sell"):
            return None

        entry = self._pullback_entry(sweep_side, ctx.df_m5)
        if entry is None:
            return None

        atr = self._atr(ctx.df_m5, self.settings.atr_period)
        if np.isnan(atr) or atr <= 0:
            return None

        structure_high, structure_low = self._swing_levels(ctx.df_m5)
        stop = self._stop_loss(sweep_side, entry, atr, structure_high, structure_low)
        risk_distance = abs(entry - stop)
        if risk_distance <= 0:
            return None

        tp1, tp2, tp3 = self._targets(sweep_side, entry, stop)
        rule_score = 0.6
        rule_score += 0.2 if bias != "neutral" else 0.0
        rule_score += 0.2 if sweep_side == bos_side else 0.0
        rule_score = min(1.0, rule_score)

        features = {
            "h1_last_close": float(ctx.df_h1["close"].iloc[-1]),
            "h1_ema20": float(self._ema(ctx.df_h1["close"], 20).iloc[-1]),
            "h1_ema50": float(self._ema(ctx.df_h1["close"], 50).iloc[-1]),
            "m15_last_close": float(ctx.df_m15["close"].iloc[-1]),
            "m5_last_close": float(ctx.df_m5["close"].iloc[-1]),
            "atr": float(atr),
            "risk_distance": float(risk_distance),
            "bias_bullish": 1.0 if bias == "bullish" else 0.0,
            "direction_buy": 1.0 if sweep_side == "buy" else 0.0,
        }

        notes = f"bias={bias}, sweep={sweep_side}, bos={bos_side}, stop_mode={self.settings.stop_loss_mode}"
        return Signal(
            market=ctx.market,  # type: ignore[arg-type]
            symbol=ctx.symbol,
            side=sweep_side,  # type: ignore[arg-type]
            entry_price=entry,
            stop_loss=stop,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            atr=atr,
            rr_to_tp1=self.settings.tp1_r_multiple,
            rule_score=rule_score,
            notes=notes,
            feature_payload=features,
        )

