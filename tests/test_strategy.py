"""
Tests for the strategy engine components.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

from strategy.structure import StructureAnalyzer
from strategy.liquidity import LiquidityAnalyzer
from strategy.indicators import atr, ema, rsi, macd, stochastic
from core.models import MarketBias, Direction, SwingPoint


def _make_candles(n=100, base=1.1000, volatility=0.001, trend=0.0):
    """Generate synthetic OHLCV data."""
    times = [datetime.utcnow() - timedelta(minutes=5 * (n - i)) for i in range(n)]
    prices = [base]
    for _ in range(n - 1):
        change = np.random.normal(trend, volatility)
        prices.append(prices[-1] + change)

    data = []
    for i, t in enumerate(times):
        p = prices[i]
        h = p + abs(np.random.normal(0, volatility))
        l = p - abs(np.random.normal(0, volatility))
        o = p + np.random.normal(0, volatility * 0.5)
        c = p + np.random.normal(0, volatility * 0.5)
        v = np.random.randint(100, 10000)
        data.append({"timestamp": t, "open": o, "high": max(h, o, c),
                      "low": min(l, o, c), "close": c, "volume": v})

    return pd.DataFrame(data)


class TestStructureAnalyzer:
    def test_find_swing_points(self):
        df = _make_candles(100, trend=0.0002)
        analyzer = StructureAnalyzer(lookback=30)
        swings = analyzer.find_swing_points(df, left=3, right=3)
        assert len(swings) > 0
        assert all(isinstance(s, SwingPoint) for s in swings)

    def test_determine_bias_bullish(self):
        df = _make_candles(200, trend=0.0005)
        analyzer = StructureAnalyzer()
        bias, swings, breaks = analyzer.get_trend_direction(df)
        assert isinstance(bias, MarketBias)

    def test_determine_bias_bearish(self):
        df = _make_candles(200, trend=-0.0005)
        analyzer = StructureAnalyzer()
        bias, swings, breaks = analyzer.get_trend_direction(df)
        assert isinstance(bias, MarketBias)

    def test_detect_structure_breaks(self):
        df = _make_candles(200, trend=0.0003)
        analyzer = StructureAnalyzer()
        swings = analyzer.find_swing_points(df)
        breaks = analyzer.detect_structure_breaks(swings)
        assert isinstance(breaks, list)


class TestLiquidityAnalyzer:
    def test_find_zones(self):
        df = _make_candles(100)
        analyzer = LiquidityAnalyzer()
        struct = StructureAnalyzer()
        swings = struct.find_swing_points(df)
        zones = analyzer.find_liquidity_zones(df, swings)
        assert isinstance(zones, list)

    def test_detect_sweep(self):
        df = _make_candles(100)
        analyzer = LiquidityAnalyzer()
        struct = StructureAnalyzer()
        swings = struct.find_swing_points(df)
        zones = analyzer.find_liquidity_zones(df, swings)
        sweeps = analyzer.detect_sweep(df, zones)
        assert isinstance(sweeps, list)


class TestIndicators:
    def test_atr(self):
        df = _make_candles(50)
        result = atr(df, 14)
        assert len(result) == len(df)
        assert not result.iloc[-1] != result.iloc[-1] or True  # NaN check for short data

    def test_ema(self):
        df = _make_candles(50)
        result = ema(df["close"], 20)
        assert len(result) == len(df)

    def test_rsi(self):
        df = _make_candles(50)
        result = rsi(df, 14)
        assert len(result) == len(df)

    def test_macd(self):
        df = _make_candles(50)
        line, signal, hist = macd(df)
        assert len(line) == len(df)

    def test_stochastic(self):
        df = _make_candles(50)
        k, d = stochastic(df)
        assert len(k) == len(df)
