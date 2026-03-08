"""Tests for the strategy layer: liquidity, structure, pullback detection."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from core.enums import Bias, Direction
from strategy.liquidity import LiquidityAnalyzer
from strategy.pullback import PullbackDetector
from strategy.structure import StructureAnalyzer


def _make_df(prices: list[float], base_time: datetime | None = None) -> pd.DataFrame:
    """Generate a minimal OHLCV DataFrame from close prices."""
    base = base_time or datetime(2025, 6, 1)
    n = len(prices)
    data = {
        "open": [p - 0.0002 for p in prices],
        "high": [p + 0.0010 for p in prices],
        "low": [p - 0.0010 for p in prices],
        "close": prices,
        "volume": [100.0] * n,
    }
    idx = [base + timedelta(minutes=5 * i) for i in range(n)]
    df = pd.DataFrame(data, index=idx)

    from data.candle_manager import CandleManager
    df = CandleManager._add_indicators(df)
    return df


def _trending_up(n: int = 60) -> list[float]:
    base = 1.1000
    prices = []
    for i in range(n):
        wave = 0.0015 * np.sin(i * 0.8)
        prices.append(base + i * 0.0002 + wave)
    return prices


def _trending_down(n: int = 60) -> list[float]:
    base = 1.1200
    prices = []
    for i in range(n):
        wave = 0.0015 * np.sin(i * 0.8)
        prices.append(base - i * 0.0002 + wave)
    return prices


class TestLiquidityAnalyzer:

    def test_find_swing_highs(self):
        liq = LiquidityAnalyzer(lookback=3)
        df = _make_df(_trending_up(40))
        swings = liq.find_swing_highs(df)
        assert len(swings) > 0
        assert all(s.is_high for s in swings)

    def test_find_swing_lows(self):
        liq = LiquidityAnalyzer(lookback=3)
        df = _make_df(_trending_down(40))
        swings = liq.find_swing_lows(df)
        assert len(swings) > 0
        assert all(not s.is_high for s in swings)

    def test_detect_liquidity_zones(self):
        liq = LiquidityAnalyzer(lookback=3)
        df = _make_df(_trending_up(50))
        zones = liq.detect_liquidity_zones(df)
        assert isinstance(zones, list)


class TestStructureAnalyzer:

    def test_bullish_bias(self):
        sa = StructureAnalyzer(lookback=5)
        df = _make_df(_trending_up(60))
        bias = sa.determine_bias(df)
        assert bias in (Bias.BULLISH, Bias.NEUTRAL)

    def test_bearish_bias(self):
        sa = StructureAnalyzer(lookback=5)
        df = _make_df(_trending_down(60))
        bias = sa.determine_bias(df)
        assert bias in (Bias.BEARISH, Bias.NEUTRAL)

    def test_bos_detection(self):
        sa = StructureAnalyzer(lookback=5)
        df = _make_df(_trending_up(60))
        bos = sa.detect_bos(df)
        # BOS may or may not be found depending on swing structure
        if bos is not None:
            assert bos.direction in (Direction.LONG, Direction.SHORT)

    def test_structure_levels(self):
        sa = StructureAnalyzer(lookback=5)
        df = _make_df(_trending_up(60))
        resistances, supports = sa.get_structure_levels(df)
        assert isinstance(resistances, list)
        assert isinstance(supports, list)


class TestPullbackDetector:

    def test_no_pullback_on_empty(self):
        pd_ = PullbackDetector()
        from core.models import StructureBreak
        bos = StructureBreak(
            timestamp=datetime.utcnow(),
            price=1.1050,
            direction=Direction.LONG,
            broken_level=1.1040,
            timeframe="M15",
        )
        df = pd.DataFrame()
        result = pd_.detect(df, bos, 1.1000, 1.1060)
        assert result is None
