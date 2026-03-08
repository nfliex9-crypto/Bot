from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategySignal:
    side: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    atr_value: float
    sweep_strength: float
    bos_strength: float
    pullback_quality: float
    atr_regime: float
    momentum: float


class LiquidityBOSPullbackStrategy:
    def __init__(self, atr_period: int = 14, lookback: int = 20) -> None:
        self.atr_period = atr_period
        self.lookback = lookback

    def _atr(self, frame: pd.DataFrame) -> pd.Series:
        high_low = frame["high"] - frame["low"]
        high_close = (frame["high"] - frame["close"].shift(1)).abs()
        low_close = (frame["low"] - frame["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(self.atr_period).mean()

    def generate_signal(self, frame: pd.DataFrame) -> StrategySignal | None:
        if len(frame) < max(self.atr_period + 5, self.lookback + 5):
            return None

        data = frame.copy().reset_index(drop=True)
        data["ema20"] = data["close"].ewm(span=20, adjust=False).mean()
        data["atr"] = self._atr(data)
        data = data.dropna().reset_index(drop=True)
        if data.empty:
            return None

        last = data.iloc[-1]
        atr = float(last["atr"])
        if atr <= 0:
            return None

        prior = data.iloc[-self.lookback - 1 : -1]
        prior_high = float(prior["high"].max())
        prior_low = float(prior["low"].min())

        bullish_sweep = bool(last["low"] < prior_low and last["close"] > prior_low)
        bearish_sweep = bool(last["high"] > prior_high and last["close"] < prior_high)
        if not bullish_sweep and not bearish_sweep:
            return None

        recent_high = float(data["high"].iloc[-12:-1].max())
        recent_low = float(data["low"].iloc[-12:-1].min())
        close_price = float(last["close"])
        ema20 = float(last["ema20"])
        ema_distance = abs(close_price - ema20) / atr
        pullback_quality = float(np.clip(1.0 - ema_distance / 1.5, 0.0, 1.0))
        if pullback_quality < 0.25:
            return None

        if bullish_sweep:
            bos_valid = close_price > recent_high
            if not bos_valid:
                return None
            stop_loss = close_price - 1.5 * atr
            side = "buy"
            sweep_strength = (prior_low - float(last["low"])) / atr
            bos_strength = (close_price - recent_high) / atr
        else:
            bos_valid = close_price < recent_low
            if not bos_valid:
                return None
            stop_loss = close_price + 1.5 * atr
            side = "sell"
            sweep_strength = (float(last["high"]) - prior_high) / atr
            bos_strength = (recent_low - close_price) / atr

        risk_unit = abs(close_price - stop_loss)
        tp1 = close_price + risk_unit if side == "buy" else close_price - risk_unit
        tp2 = close_price + 2 * risk_unit if side == "buy" else close_price - 2 * risk_unit
        tp3 = close_price + 3 * risk_unit if side == "buy" else close_price - 3 * risk_unit
        atr_regime = (atr / close_price) * 100.0
        momentum = float((data["close"].iloc[-1] - data["close"].iloc[-5]) / atr)

        return StrategySignal(
            side=side,
            entry_price=close_price,
            stop_loss=float(stop_loss),
            tp1=float(tp1),
            tp2=float(tp2),
            tp3=float(tp3),
            atr_value=atr,
            sweep_strength=float(np.clip(sweep_strength, 0.0, 3.0)),
            bos_strength=float(np.clip(bos_strength, 0.0, 3.0)),
            pullback_quality=pullback_quality,
            atr_regime=float(np.clip(atr_regime, 0.0, 5.0)),
            momentum=float(np.clip(momentum, -3.0, 3.0)),
        )
