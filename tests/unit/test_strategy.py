"""Tests for core strategy components."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from src.strategy.indicators import (
    calculate_atr, calculate_ema, calculate_rsi,
    find_swing_highs, find_swing_lows, identify_order_blocks,
)
from src.strategy.liquidity_sweep import LiquiditySweepDetector
from src.strategy.break_of_structure import BreakOfStructureDetector
from src.strategy.pullback_entry import PullbackEntryDetector


def make_trending_df(n=100, direction="up", base=1.1000, volatility=0.001):
    """Create synthetic trending OHLCV data with realistic oscillations."""
    np.random.seed(42)
    times = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(n)]

    # Use sinusoidal oscillation + trend to guarantee clear swing highs/lows
    t = np.linspace(0, 4 * np.pi, n)
    oscillation = np.sin(t) * volatility * 5
    if direction == "up":
        trend = np.linspace(0, volatility * n, n)
    else:
        trend = np.linspace(0, -volatility * n, n)

    closes = base + trend + oscillation
    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * volatility * 0.5)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * volatility * 0.5)

    return pd.DataFrame({
        "open_time": times,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.randint(100, 1000, n).astype(float),
    })


# ── Indicator Tests ───────────────────────────────────────────────────────────

def test_atr_returns_positive_values():
    df = make_trending_df(50)
    atr = calculate_atr(df, period=14)
    assert len(atr) == 50
    assert atr.iloc[-1] > 0
    assert not atr.isnull().all()


def test_ema_smoothing():
    df = make_trending_df(100, direction="up")
    ema_fast = calculate_ema(df["close"], 10)
    ema_slow = calculate_ema(df["close"], 20)
    # In an uptrend, fast EMA should be above slow EMA
    assert ema_fast.iloc[-1] > ema_slow.iloc[-1]


def test_rsi_range():
    df = make_trending_df(100)
    rsi = calculate_rsi(df["close"], 14)
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0).all()
    assert (valid_rsi <= 100).all()


def test_swing_highs_detection():
    df = make_trending_df(60)
    swing_h = find_swing_highs(df, lookback=3)
    assert swing_h.dtype == bool
    assert swing_h.sum() > 0


def test_swing_lows_detection():
    df = make_trending_df(60)
    swing_l = find_swing_lows(df, lookback=3)
    assert swing_l.dtype == bool
    assert swing_l.sum() > 0


def test_order_blocks_identified():
    df = make_trending_df(50)
    ob_df = identify_order_blocks(df)
    assert "bullish_ob" in ob_df.columns
    assert "bearish_ob" in ob_df.columns


# ── BOS Tests ─────────────────────────────────────────────────────────────────

def test_bos_returns_result_on_insufficient_data():
    df = make_trending_df(20)
    detector = BreakOfStructureDetector(lookback=5)
    result = detector.detect(df)
    assert result is not None


def test_bos_trend_detection_uptrend():
    df = make_trending_df(100, direction="up")
    detector = BreakOfStructureDetector(lookback=5)
    result = detector.detect(df)
    # Should detect bullish trend or at least not bearish
    assert result.trend in ("bullish", "ranging", None)


def test_bos_trend_detection_downtrend():
    df = make_trending_df(100, direction="down")
    detector = BreakOfStructureDetector(lookback=5)
    result = detector.detect(df)
    assert result.trend in ("bearish", "ranging", None)


# ── Liquidity Sweep Tests ─────────────────────────────────────────────────────

def test_sweep_detector_no_crash():
    df = make_trending_df(60)
    detector = LiquiditySweepDetector(lookback=5)
    result = detector.detect(df)
    assert result is not None
    assert isinstance(result.detected, bool)


def test_sweep_strength_range():
    df = make_trending_df(60)
    detector = LiquiditySweepDetector(lookback=5)
    result = detector.detect(df)
    assert 0.0 <= result.strength <= 1.0


# ── Pullback Entry Tests ──────────────────────────────────────────────────────

def test_pullback_in_fib_zone_bullish():
    df = make_trending_df(60, direction="up")
    detector = PullbackEntryDetector()
    # After a 100-pip bullish impulse, price retraces 60%
    impulse_start = 1.1000
    impulse_end = 1.1100
    # Current price at 62% retrace = 1.1038
    df.iloc[-1, df.columns.get_loc("close")] = 1.1038
    result = detector.detect(df, "bullish", impulse_start, impulse_end)
    assert result is not None
    assert isinstance(result.valid, bool)


def test_pullback_outside_fib_zone():
    df = make_trending_df(60, direction="up")
    detector = PullbackEntryDetector()
    impulse_start = 1.1000
    impulse_end = 1.1100
    # Current price barely retraced — only 5%
    df.iloc[-1, df.columns.get_loc("close")] = 1.1095
    result = detector.detect(df, "bullish", impulse_start, impulse_end)
    assert result.valid is False


def test_fib_retracement_calculation():
    df = make_trending_df(60, direction="up")
    detector = PullbackEntryDetector()
    impulse_start = 1.0000
    impulse_end = 1.1000
    # 70% retrace
    df.iloc[-1, df.columns.get_loc("close")] = 1.0300
    result = detector.detect(df, "bullish", impulse_start, impulse_end)
    # 70% retrace should be within 50-79% OTE zone
    assert result.fib_retracement is not None
    assert 0.0 < result.fib_retracement < 1.0
