from dataclasses import dataclass

import pandas as pd

from app.config import Settings
from app.strategy.indicators import calculate_atr, last_structure_levels, market_bias_h1, volatility_regime


@dataclass
class TradeSetup:
    should_trade: bool
    side: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    confidence_features: dict | None = None
    notes: list[str] | None = None


class LiquidityBosPullbackStrategy:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _detect_liquidity_sweep(self, df_m5: pd.DataFrame) -> dict:
        if len(df_m5) < 15:
            return {"sweep": False}
        recent = df_m5.iloc[-10:]
        candle = df_m5.iloc[-1]
        prev_high = recent["high"].iloc[:-1].max()
        prev_low = recent["low"].iloc[:-1].min()

        bullish_sweep = candle["low"] < prev_low and candle["close"] > prev_low
        bearish_sweep = candle["high"] > prev_high and candle["close"] < prev_high
        return {
            "sweep": bullish_sweep or bearish_sweep,
            "bullish_sweep": bool(bullish_sweep),
            "bearish_sweep": bool(bearish_sweep),
            "swept_high": float(prev_high),
            "swept_low": float(prev_low),
        }

    def _detect_bos(self, df_m15: pd.DataFrame) -> dict:
        if len(df_m15) < 30:
            return {"bos": False}
        last_high, last_low = last_structure_levels(df_m15.iloc[:-1])
        close_now = df_m15["close"].iloc[-1]

        bullish_bos = last_high is not None and close_now > last_high
        bearish_bos = last_low is not None and close_now < last_low
        return {
            "bos": bullish_bos or bearish_bos,
            "bullish_bos": bool(bullish_bos),
            "bearish_bos": bool(bearish_bos),
            "structure_high": last_high,
            "structure_low": last_low,
        }

    def _pullback_entry(self, df_m5: pd.DataFrame, side: str, anchor_level: float | None) -> bool:
        if anchor_level is None or len(df_m5) < 4:
            return False
        close_now = float(df_m5["close"].iloc[-1])
        close_prev = float(df_m5["close"].iloc[-2])

        # Pullback confirmation: revisit anchor then resume direction.
        if side == "buy":
            touched = float(df_m5["low"].iloc[-3:-1].min()) <= anchor_level
            resumed = close_now > close_prev
            return touched and resumed
        touched = float(df_m5["high"].iloc[-3:-1].max()) >= anchor_level
        resumed = close_now < close_prev
        return touched and resumed

    def analyze(self, df_h1: pd.DataFrame, df_m15: pd.DataFrame, df_m5: pd.DataFrame) -> TradeSetup:
        notes: list[str] = []
        bias = market_bias_h1(df_h1)
        sweep = self._detect_liquidity_sweep(df_m5)
        bos = self._detect_bos(df_m15)

        if not sweep.get("sweep"):
            return TradeSetup(False, notes=["No liquidity sweep on M5"])
        if not bos.get("bos"):
            return TradeSetup(False, notes=["No break of structure on M15"])

        side: str | None = None
        anchor_level: float | None = None
        if bias == "bullish" and sweep.get("bullish_sweep") and bos.get("bullish_bos"):
            side = "buy"
            anchor_level = bos.get("structure_high")
        elif bias == "bearish" and sweep.get("bearish_sweep") and bos.get("bearish_bos"):
            side = "sell"
            anchor_level = bos.get("structure_low")
        else:
            return TradeSetup(False, notes=["Bias and setup are not aligned"])

        if not self._pullback_entry(df_m5, side, anchor_level):
            return TradeSetup(False, notes=["No valid pullback entry on M5"])

        entry = float(df_m5["close"].iloc[-1])
        atr_value = float(calculate_atr(df_m5, self.settings.atr_period).iloc[-1])

        structure_high, structure_low = last_structure_levels(df_m5)
        if self.settings.use_structure_stop and structure_high is not None and structure_low is not None:
            stop_loss = structure_low if side == "buy" else structure_high
            notes.append("Using structure stop")
        else:
            stop_loss = entry - (atr_value * self.settings.atr_multiplier) if side == "buy" else entry + (
                atr_value * self.settings.atr_multiplier
            )
            notes.append("Using ATR stop")

        risk_distance = abs(entry - stop_loss)
        if risk_distance <= 0:
            return TradeSetup(False, notes=["Invalid stop-loss distance"])

        if side == "buy":
            tp1 = entry + (1.0 * risk_distance)
            tp2 = entry + (1.5 * risk_distance)
            tp3 = entry + (2.0 * risk_distance)
        else:
            tp1 = entry - (1.0 * risk_distance)
            tp2 = entry - (1.5 * risk_distance)
            tp3 = entry - (2.0 * risk_distance)

        features = {
            "bias": 1 if bias == "bullish" else -1,
            "atr": atr_value,
            "volatility_regime": volatility_regime(df_m15),
            "risk_distance": risk_distance,
            "bos_flag": 1.0,
            "sweep_flag": 1.0,
        }

        return TradeSetup(
            should_trade=True,
            side=side,
            entry=entry,
            stop_loss=float(stop_loss),
            tp1=float(tp1),
            tp2=float(tp2),
            tp3=float(tp3),
            confidence_features=features,
            notes=notes,
        )

