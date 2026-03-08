from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.db.models import MarketType, OrderSide


@dataclass
class StrategySignal:
    symbol: str
    market: MarketType
    timeframe: str
    side: OrderSide
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rationale: str
    features: dict[str, float | int]


class SmartMoneyStrategy:
    def analyze(self, symbol: str, market: MarketType, timeframe: str, df: pd.DataFrame) -> StrategySignal | None:
        if len(df) < 60:
            return None

        frame = df.copy().reset_index(drop=True)
        frame["atr"] = self._atr(frame)
        frame["ema_fast"] = frame["close"].ewm(span=20, adjust=False).mean()
        frame["ema_slow"] = frame["close"].ewm(span=50, adjust=False).mean()
        frame["returns"] = frame["close"].pct_change().fillna(0.0)
        frame["volume_zscore"] = (
            (frame["volume"] - frame["volume"].rolling(20).mean())
            / frame["volume"].rolling(20).std().replace(0, np.nan)
        ).fillna(0.0)

        latest = frame.iloc[-1]
        previous = frame.iloc[:-1]
        recent_window = previous.tail(20)

        if recent_window.empty:
            return None

        prior_high = float(recent_window["high"].max())
        prior_low = float(recent_window["low"].min())
        atr = float(latest["atr"])
        close = float(latest["close"])

        bullish_sweep = float(latest["low"]) < prior_low and close > prior_low
        bearish_sweep = float(latest["high"]) > prior_high and close < prior_high

        bullish_bos = close > float(previous.tail(10)["high"].max())
        bearish_bos = close < float(previous.tail(10)["low"].min())

        trend_up = float(latest["ema_fast"]) > float(latest["ema_slow"])
        trend_down = float(latest["ema_fast"]) < float(latest["ema_slow"])

        bullish_pullback_ratio = self._safe_ratio(close - prior_low, max(close - prior_low, atr))
        bearish_pullback_ratio = self._safe_ratio(prior_high - close, max(prior_high - close, atr))

        bullish_score = sum([bullish_sweep, bullish_bos, trend_up, bullish_pullback_ratio > 0.35])
        bearish_score = sum([bearish_sweep, bearish_bos, trend_down, bearish_pullback_ratio > 0.35])

        if bullish_score < 2 and bearish_score < 2:
            return None

        if bullish_score >= bearish_score:
            stop_loss = min(prior_low, float(latest["low"])) - atr * 0.5
            risk_distance = close - stop_loss
            return StrategySignal(
                symbol=symbol,
                market=market,
                timeframe=timeframe,
                side=OrderSide.LONG,
                entry_price=close,
                stop_loss=stop_loss,
                tp1=close + risk_distance,
                tp2=close + risk_distance * 2,
                tp3=close + risk_distance * 3,
                rationale="Bullish liquidity sweep followed by structure break and pullback continuation bias.",
                features={
                    "atr": atr,
                    "atr_ratio": self._safe_ratio(atr, close),
                    "liquidity_sweep": int(bullish_sweep),
                    "bos": int(bullish_bos),
                    "pullback_ratio": bullish_pullback_ratio,
                    "trend_bias": 1,
                    "volume_zscore": float(latest["volume_zscore"]),
                    "volatility": float(frame["returns"].tail(20).std()),
                },
            )

        stop_loss = max(prior_high, float(latest["high"])) + atr * 0.5
        risk_distance = stop_loss - close
        return StrategySignal(
            symbol=symbol,
            market=market,
            timeframe=timeframe,
            side=OrderSide.SHORT,
            entry_price=close,
            stop_loss=stop_loss,
            tp1=close - risk_distance,
            tp2=close - risk_distance * 2,
            tp3=close - risk_distance * 3,
            rationale="Bearish liquidity sweep followed by downside structure break and pullback continuation bias.",
            features={
                "atr": atr,
                "atr_ratio": self._safe_ratio(atr, close),
                "liquidity_sweep": int(bearish_sweep),
                "bos": int(bearish_bos),
                "pullback_ratio": bearish_pullback_ratio,
                "trend_bias": -1,
                "volume_zscore": float(latest["volume_zscore"]),
                "volatility": float(frame["returns"].tail(20).std()),
            },
        )

    @staticmethod
    def _atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = frame["high"] - frame["low"]
        high_close = (frame["high"] - frame["close"].shift(1)).abs()
        low_close = (frame["low"] - frame["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean().bfill()
        return atr

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        value = numerator / denominator
        return float(max(0.0, min(2.0, value)))
