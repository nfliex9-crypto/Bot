"""Tests for the strategy engine components."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from app.strategy.indicators import (
    calculate_atr, calculate_rsi, calculate_ema,
    calculate_macd, find_swing_highs, find_swing_lows,
    identify_order_blocks,
)
from app.strategy.liquidity_sweep import LiquiditySweepDetector
from app.strategy.break_of_structure import BreakOfStructureDetector
from app.strategy.pullback_entry import PullbackEntryModel


def generate_test_data(n=300, trend="up", seed=42):
    np.random.seed(seed)
    base_price = 1.1000
    timestamps = pd.date_range(
        end=datetime.now(timezone.utc), periods=n, freq="h"
    )

    if trend == "up":
        drift = 0.0003
    elif trend == "down":
        drift = -0.0003
    else:
        drift = 0.0

    returns = np.random.normal(drift, 0.001, n)
    closes = base_price * np.exp(np.cumsum(returns))
    highs = closes * (1 + np.abs(np.random.normal(0, 0.0005, n)))
    lows = closes * (1 - np.abs(np.random.normal(0, 0.0005, n)))
    opens = np.roll(closes, 1)
    opens[0] = base_price
    volumes = np.random.randint(100, 10000, n).astype(float)

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


class TestIndicators:
    def test_atr_calculation(self):
        df = generate_test_data()
        atr = calculate_atr(df, period=14)
        assert len(atr) == len(df)
        assert atr.iloc[14:].notna().all()
        assert (atr.iloc[14:] > 0).all()

    def test_rsi_calculation(self):
        df = generate_test_data()
        rsi = calculate_rsi(df["close"])
        valid_rsi = rsi.dropna()
        assert len(valid_rsi) > 0
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_ema_calculation(self):
        df = generate_test_data()
        ema = calculate_ema(df["close"], 20)
        assert len(ema) == len(df)
        assert ema.iloc[-1] > 0

    def test_macd_calculation(self):
        df = generate_test_data()
        macd_line, signal_line, histogram = calculate_macd(df["close"])
        assert len(macd_line) == len(df)
        assert len(signal_line) == len(df)
        assert len(histogram) == len(df)

    def test_swing_highs(self):
        df = generate_test_data()
        swings = find_swing_highs(df, lookback=5)
        assert isinstance(swings, pd.Series)
        assert swings.dtype == bool
        assert swings.sum() > 0

    def test_swing_lows(self):
        df = generate_test_data()
        swings = find_swing_lows(df, lookback=5)
        assert isinstance(swings, pd.Series)
        assert swings.dtype == bool
        assert swings.sum() > 0

    def test_order_blocks(self):
        df = generate_test_data()
        obs = identify_order_blocks(df)
        assert isinstance(obs, list)
        for ob in obs:
            assert "type" in ob
            assert ob["type"] in ("bullish", "bearish")
            assert "high" in ob
            assert "low" in ob


class TestLiquiditySweep:
    def test_detector_init(self):
        detector = LiquiditySweepDetector()
        assert detector.swing_lookback == 10
        assert detector.min_rejection_ratio == 0.5

    def test_detect_returns_list(self):
        df = generate_test_data(n=300)
        detector = LiquiditySweepDetector()
        sweeps = detector.detect(df)
        assert isinstance(sweeps, list)

    def test_detect_with_insufficient_data(self):
        df = generate_test_data(n=10)
        detector = LiquiditySweepDetector()
        sweeps = detector.detect(df)
        assert sweeps == []

    def test_get_latest_sweep(self):
        df = generate_test_data(n=500, seed=123)
        detector = LiquiditySweepDetector(
            min_rejection_ratio=0.3, sweep_threshold_atr_mult=0.5
        )
        sweep = detector.get_latest_sweep(df, lookback_candles=50)
        if sweep is not None:
            assert sweep.direction in ("bullish", "bearish")
            assert 0 <= sweep.rejection_strength <= 1.0


class TestBreakOfStructure:
    def test_detector_init(self):
        detector = BreakOfStructureDetector()
        assert detector.swing_lookback == 10
        assert detector.trend_ema_period == 50

    def test_detect_returns_list(self):
        df = generate_test_data(n=300)
        detector = BreakOfStructureDetector()
        breaks = detector.detect(df)
        assert isinstance(breaks, list)

    def test_detect_with_insufficient_data(self):
        df = generate_test_data(n=20)
        detector = BreakOfStructureDetector()
        breaks = detector.detect(df)
        assert breaks == []

    def test_get_latest_bos(self):
        df = generate_test_data(n=500, trend="up")
        detector = BreakOfStructureDetector()
        bos = detector.get_latest_bos(df, lookback_candles=50)
        if bos is not None:
            assert bos.direction in ("bullish", "bearish")
            assert 0 <= bos.strength <= 1.0
            assert bos.broken_level > 0


class TestPullbackEntry:
    def test_model_init(self):
        model = PullbackEntryModel()
        assert model.fib_entry_zone == (0.5, 0.786)
        assert model.min_rr_ratio == 2.0

    def test_find_entries_returns_list(self):
        df = generate_test_data(n=300)
        model = PullbackEntryModel()
        setups = model.find_entries(df, "EURUSD", "H1")
        assert isinstance(setups, list)

    def test_find_entries_with_insufficient_data(self):
        df = generate_test_data(n=10)
        model = PullbackEntryModel()
        setups = model.find_entries(df, "EURUSD", "H1")
        assert setups == []

    def test_trade_setup_fields(self):
        df = generate_test_data(n=300, trend="up")
        model = PullbackEntryModel(min_rr_ratio=1.0)
        setups = model.find_entries(df, "EURUSD", "H1")
        for setup in setups:
            assert setup.direction in ("long", "short")
            assert setup.entry_price > 0
            assert setup.stop_loss > 0
            assert setup.take_profit_1 > 0
            assert setup.risk_reward_ratio > 0
            assert 0 <= setup.confidence <= 1.0
            assert setup.symbol == "EURUSD"
            assert setup.timeframe == "H1"
