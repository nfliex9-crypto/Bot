"""
Auto-generated strategy module from strategy discovery engine.
Generated at: 2026-03-09T17:21:58.891309+00:00

This module is intentionally simple and deterministic.
"""
import pandas as pd
import numpy as np

from app.core.strategy.pullback_entry import EntryResult


class AutoDiscoveredStrategy:
    strategy_id = "STRAT_0464"
    name = "Trend Following 464"
    primary_logic = "trend_following"
    confirmation_logic = "none"
    parameters = {"bb_period": 26.0, "bb_std": 1.8, "breakout_window": 40.0, "ema_fast": 9.0, "ema_slow": 34.0, "exit_on_opposite": 0.0, "macd_hist_min": 5e-05, "max_hold_bars": 72.0, "risk_fraction": 0.005, "rsi_high": 72.0, "rsi_low": 28.0, "sl_atr_mult": 2.2, "sma_period": 100.0, "structure_window": 30.0, "sweep_atr_buffer": 0.1, "tp_rr": 2.0, "vol_expansion_k": 1.8}

    def _atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                df["high"] - df["low"],
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    def _rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def _signal(self, df: pd.DataFrame) -> str:
        p = self.parameters
        close = df["close"]
        high = df["high"]
        low = df["low"]
        atr = self._atr(df)
        rsi = self._rsi(df)
        ema_fast = close.ewm(span=int(p["ema_fast"]), adjust=False).mean()
        ema_slow = close.ewm(span=int(p["ema_slow"]), adjust=False).mean()
        prev_high = high.rolling(int(p["breakout_window"])).max().shift(1)
        prev_low = low.rolling(int(p["breakout_window"])).min().shift(1)
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal
        typical = (high + low + close) / 3.0
        vwap = (typical * df["volume"].fillna(0)).rolling(30).sum() / df["volume"].rolling(30).sum().replace(0, np.nan)

        long_cond = (
            (ema_fast > ema_slow)
            & (close > ema_fast)
            & (close > prev_high)
            & (macd_hist > p["macd_hist_min"])
            & (rsi > 52)
            & (close > vwap)
        )
        short_cond = (
            (ema_fast < ema_slow)
            & (close < ema_fast)
            & (close < prev_low)
            & (macd_hist < -p["macd_hist_min"])
            & (rsi < 48)
            & (close < vwap)
        )

        if long_cond.iloc[-1] and not short_cond.iloc[-1]:
            return "long"
        if short_cond.iloc[-1] and not long_cond.iloc[-1]:
            return "short"
        return "flat"

    def analyze(self, symbol: str, m5_df: pd.DataFrame) -> EntryResult:
        if m5_df is None or len(m5_df) < 120:
            return EntryResult(valid=False)

        df = m5_df.copy()
        atr = self._atr(df).iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return EntryResult(valid=False)

        direction = self._signal(df)
        if direction == "flat":
            return EntryResult(valid=False)

        entry = float(df.iloc[-1]["close"])
        sl_atr_mult = float(self.parameters["sl_atr_mult"])
        rr = float(self.parameters["tp_rr"])
        risk = atr * sl_atr_mult

        if direction == "long":
            stop_loss = entry - risk
            tp1 = entry + risk * 1.0
            tp2 = entry + risk * min(1.5, rr)
            tp3 = entry + risk * rr
        else:
            stop_loss = entry + risk
            tp1 = entry - risk * 1.0
            tp2 = entry - risk * min(1.5, rr)
            tp3 = entry - risk * rr

        return EntryResult(
            valid=True,
            direction=direction,
            entry_price=entry,
            stop_loss=float(stop_loss),
            take_profit_1=float(tp1),
            take_profit_2=float(tp2),
            take_profit_3=float(tp3),
            risk_amount_pips=float(abs(entry - stop_loss)),
            risk_reward=float(rr),
            entry_zone_type="auto_discovered",
            atr=float(atr),
            sl_type="atr",
            confidence_boost=0.05,
        )
