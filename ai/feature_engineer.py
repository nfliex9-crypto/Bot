from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core.models import Direction, MultiTimeframeAnalysis
from utils.helpers import ewm_atr, find_swing_highs, find_swing_lows


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = series.ewm(span=fast, adjust=False).mean()
    slow_ema = series.ewm(span=slow, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> tuple:
    lowest_low = df["low"].rolling(k).min()
    highest_high = df["high"].rolling(k).max()
    pct_k = 100 * (df["close"] - lowest_low) / (highest_high - lowest_low + 1e-10)
    pct_d = pct_k.rolling(d).mean()
    return pct_k, pct_d


def _cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma) / (0.015 * mad + 1e-10)


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


class FeatureEngineer:
    """
    Constructs a rich feature vector from OHLCV data and MTF analysis
    for the RandomForest classifier.
    """

    # Feature names in insertion order
    FEATURE_NAMES: List[str] = [
        # Price-derived
        "atr_norm",
        "body_size_norm",
        "upper_wick_norm",
        "lower_wick_norm",
        "candle_direction",
        # Momentum
        "rsi_14",
        "rsi_slope",
        "macd_hist_norm",
        "stoch_k",
        "stoch_d",
        "stoch_kd_diff",
        "cci_20",
        # Trend
        "ema_9_slope",
        "ema_21_slope",
        "ema_9_21_cross",
        "price_vs_ema21",
        "price_vs_ema50",
        # Volatility
        "atr_vs_atr20",
        "bb_width_norm",
        "bb_position",
        # Volume
        "vol_ratio",
        "vol_trend",
        # Structure
        "dist_to_swing_high",
        "dist_to_swing_low",
        "swing_range_norm",
        # Session / Context
        "session_london",
        "session_ny",
        "session_overlap",
        # MTF alignment
        "h1_bias_bull",
        "h1_bias_bear",
        "m15_uptrend",
        "m15_downtrend",
        "sweep_confirmed",
        "sweep_strength",
        "bos_confirmed",
        "pullback_valid",
    ]

    def build(
        self,
        df: pd.DataFrame,
        mta: Optional[MultiTimeframeAnalysis] = None,
        session_flags: Optional[Dict[str, bool]] = None,
    ) -> Optional[np.ndarray]:
        """
        Build feature vector for the last row of df.
        Returns None if there is not enough data.
        """
        if len(df) < 60:
            return None

        try:
            return self._extract(df, mta, session_flags)
        except Exception:
            return None

    def build_batch(
        self,
        df: pd.DataFrame,
        mta_list: Optional[List[Optional[MultiTimeframeAnalysis]]] = None,
    ) -> np.ndarray:
        """Build feature matrix for model training from historical data."""
        rows = []
        for i in range(60, len(df)):
            slice_df = df.iloc[: i + 1]
            mta = mta_list[i] if mta_list else None
            feat = self._extract(slice_df, mta, session_flags=None)
            rows.append(feat)
        return np.array(rows, dtype=np.float32)

    # ------------------------------------------------------------------
    def _extract(
        self,
        df: pd.DataFrame,
        mta: Optional[MultiTimeframeAnalysis],
        session_flags: Optional[Dict[str, bool]],
    ) -> np.ndarray:
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"] if "volume" in df.columns else pd.Series(1.0, index=df.index)

        atr = ewm_atr(df, 14)
        atr_val = float(atr.iloc[-1])
        atr20 = float(ewm_atr(df, 20).iloc[-1])

        last = df.iloc[-1]
        body = abs(last["close"] - last["open"])
        candle_range = last["high"] - last["low"] + 1e-10

        # Candle features
        feat_body = body / candle_range
        feat_upper_wick = (last["high"] - max(last["open"], last["close"])) / candle_range
        feat_lower_wick = (min(last["open"], last["close"]) - last["low"]) / candle_range
        feat_candle_dir = 1.0 if last["close"] > last["open"] else -1.0
        feat_atr_norm = atr_val / (last["close"] + 1e-10)

        # RSI
        rsi = _rsi(close, 14)
        rsi_val = float(rsi.iloc[-1]) / 100.0
        rsi_slope = float(rsi.diff(3).iloc[-1]) / 100.0

        # MACD
        macd_line, sig_line, hist = _macd(close)
        hist_val = float(hist.iloc[-1]) / (last["close"] + 1e-10)

        # Stochastic
        stoch_k, stoch_d = _stochastic(df)
        sk = float(stoch_k.iloc[-1]) / 100.0
        sd = float(stoch_d.iloc[-1]) / 100.0

        # CCI
        cci = _cci(df)
        cci_val = float(np.clip(cci.iloc[-1] / 200.0, -1, 1))

        # EMAs
        ema9 = close.ewm(span=9, adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        ema9_slope = float(ema9.diff(3).iloc[-1]) / (last["close"] + 1e-10)
        ema21_slope = float(ema21.diff(3).iloc[-1]) / (last["close"] + 1e-10)
        ema9_21_cross = 1.0 if float(ema9.iloc[-1]) > float(ema21.iloc[-1]) else -1.0
        price_vs_ema21 = (last["close"] - float(ema21.iloc[-1])) / (atr_val + 1e-10)
        price_vs_ema50 = (last["close"] - float(ema50.iloc[-1])) / (atr_val + 1e-10)

        # Bollinger Bands
        bb_upper, bb_mid, bb_lower = _bollinger_bands(close)
        bb_width = (float(bb_upper.iloc[-1]) - float(bb_lower.iloc[-1])) / (last["close"] + 1e-10)
        bb_pos = (last["close"] - float(bb_lower.iloc[-1])) / (
            float(bb_upper.iloc[-1]) - float(bb_lower.iloc[-1]) + 1e-10
        )

        # Volatility
        atr_ratio = atr_val / (atr20 + 1e-10)

        # Volume
        vol_mean = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = float(volume.iloc[-1]) / (vol_mean + 1e-10)
        vol_trend = float(volume.diff(5).iloc[-1]) / (vol_mean + 1e-10)

        # Swing levels
        sh_mask = find_swing_highs(high, 5)
        sl_mask = find_swing_lows(low, 5)
        swing_highs = high[sh_mask].dropna()
        swing_lows = low[sl_mask].dropna()
        nearest_high = float(swing_highs.iloc[-1]) if not swing_highs.empty else last["close"]
        nearest_low = float(swing_lows.iloc[-1]) if not swing_lows.empty else last["close"]
        dist_high = (nearest_high - last["close"]) / (atr_val + 1e-10)
        dist_low = (last["close"] - nearest_low) / (atr_val + 1e-10)
        swing_range = (nearest_high - nearest_low) / (atr_val + 1e-10)

        # Session flags
        sf = session_flags or {}
        sess_london = float(sf.get("london", 0))
        sess_ny = float(sf.get("new_york", 0))
        sess_overlap = float(sf.get("overlap", 0))

        # MTF alignment features
        from core.models import MarketBias, TrendStructure

        h1_bull = h1_bear = m15_up = m15_down = 0.0
        sweep_conf = sweep_str = bos_conf = pb_valid = 0.0

        if mta:
            h1_bull = 1.0 if mta.h1_bias == MarketBias.BULLISH else 0.0
            h1_bear = 1.0 if mta.h1_bias == MarketBias.BEARISH else 0.0
            m15_up = 1.0 if mta.m15_structure == TrendStructure.UPTREND else 0.0
            m15_down = 1.0 if mta.m15_structure == TrendStructure.DOWNTREND else 0.0
            if mta.sweep_signal and mta.sweep_signal.confirmed:
                sweep_conf = 1.0
                sweep_str = mta.sweep_signal.strength
            if mta.bos_signal and mta.bos_signal.confirmed:
                bos_conf = 1.0
            if mta.pullback_signal and mta.pullback_signal.valid:
                pb_valid = 1.0

        features = np.array(
            [
                feat_atr_norm,
                feat_body,
                feat_upper_wick,
                feat_lower_wick,
                feat_candle_dir,
                rsi_val,
                rsi_slope,
                hist_val,
                sk,
                sd,
                sk - sd,
                cci_val,
                ema9_slope,
                ema21_slope,
                ema9_21_cross,
                price_vs_ema21,
                price_vs_ema50,
                atr_ratio,
                bb_width,
                bb_pos,
                vol_ratio,
                vol_trend,
                dist_high,
                dist_low,
                swing_range,
                sess_london,
                sess_ny,
                sess_overlap,
                h1_bull,
                h1_bear,
                m15_up,
                m15_down,
                sweep_conf,
                sweep_str,
                bos_conf,
                pb_valid,
            ],
            dtype=np.float32,
        )
        return np.nan_to_num(features, nan=0.0, posinf=5.0, neginf=-5.0)
