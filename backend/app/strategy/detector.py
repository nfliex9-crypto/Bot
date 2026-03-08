from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategySignal:
    market: str
    symbol: str
    side: str
    entry_price: float
    strategy_score: float
    reason: str
    features: dict


class SmartMoneyStrategy:
    """Liquidity sweep + BOS + pullback model."""

    def __init__(self, lookback: int = 30):
        self.lookback = lookback

    def _atr(self, df: pd.DataFrame, period: int = 14) -> float:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        return float(atr) if pd.notna(atr) else float(true_range.tail(period).mean())

    def generate_signal(self, market: str, symbol: str, df: pd.DataFrame) -> StrategySignal | None:
        if len(df) < max(self.lookback, 50):
            return None

        candles = df.copy().reset_index(drop=True)
        recent = candles.tail(self.lookback)
        last = candles.iloc[-1]
        prev = candles.iloc[-2]

        sweep_high = float(recent["high"].iloc[:-1].max())
        sweep_low = float(recent["low"].iloc[:-1].min())

        bearish_sweep = last["high"] > sweep_high and last["close"] < sweep_high
        bullish_sweep = last["low"] < sweep_low and last["close"] > sweep_low

        swing_high = float(candles["high"].iloc[-15:-5].max())
        swing_low = float(candles["low"].iloc[-15:-5].min())

        bos_bull = prev["close"] <= swing_high and last["close"] > swing_high
        bos_bear = prev["close"] >= swing_low and last["close"] < swing_low

        atr = max(self._atr(candles), 1e-8)
        momentum = float((candles["close"].iloc[-1] - candles["close"].iloc[-6]) / atr)

        impulse_high = float(candles["high"].iloc[-8:-1].max())
        impulse_low = float(candles["low"].iloc[-8:-1].min())
        midpoint = (impulse_high + impulse_low) / 2

        touched_midpoint = last["low"] <= midpoint <= last["high"]

        signal_side = None
        reason = []

        if bullish_sweep and bos_bull and touched_midpoint and momentum > 0:
            signal_side = "BUY"
            reason = ["liquidity_sweep_low", "bos_up", "pullback_midpoint"]
        elif bearish_sweep and bos_bear and touched_midpoint and momentum < 0:
            signal_side = "SELL"
            reason = ["liquidity_sweep_high", "bos_down", "pullback_midpoint"]

        if not signal_side:
            return None

        sweep_strength = float(abs(last["close"] - (sweep_low if signal_side == "BUY" else sweep_high)) / atr)
        bos_strength = float(abs(last["close"] - (swing_high if signal_side == "BUY" else swing_low)) / atr)
        pullback_depth = float(abs(last["close"] - midpoint) / atr)
        range_factor = float((last["high"] - last["low"]) / atr)

        strategy_score = float(np.clip((sweep_strength + bos_strength + (1 - min(pullback_depth, 1))) / 3, 0, 1))

        features = {
            "atr": atr,
            "momentum": momentum,
            "sweep_strength": sweep_strength,
            "bos_strength": bos_strength,
            "pullback_depth": pullback_depth,
            "range_factor": range_factor,
            "close": float(last["close"]),
            "volume": float(last.get("volume", 0.0)),
        }

        return StrategySignal(
            market=market,
            symbol=symbol,
            side=signal_side,
            entry_price=float(last["close"]),
            strategy_score=strategy_score,
            reason=",".join(reason),
            features=features,
        )
