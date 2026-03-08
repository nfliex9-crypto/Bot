from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.core.config import Settings
from app.domain.models import Market, TradeDirection
from app.domain.models import MarketSnapshot
from app.services.strategy import LiquiditySweepBosPullbackStrategy


def _build_frame(rows: list[dict[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.date_range("2026-01-01", periods=len(frame), freq="5min", tz="UTC")
    return frame.set_index("timestamp")


def test_strategy_generates_long_setup_on_aligned_structure() -> None:
    settings = Settings(stop_method="atr")
    strategy = LiquiditySweepBosPullbackStrategy(settings)

    h1 = _build_frame(
        [
            {"open": 1.00, "high": 1.02, "low": 0.99, "close": 1.01, "volume": 100},
            {"open": 1.01, "high": 1.03, "low": 1.00, "close": 1.02, "volume": 100},
            {"open": 1.02, "high": 1.05, "low": 1.01, "close": 1.04, "volume": 100},
            {"open": 1.04, "high": 1.06, "low": 1.03, "close": 1.05, "volume": 100},
            {"open": 1.05, "high": 1.08, "low": 1.04, "close": 1.07, "volume": 100},
            {"open": 1.07, "high": 1.10, "low": 1.06, "close": 1.09, "volume": 100},
            {"open": 1.09, "high": 1.11, "low": 1.08, "close": 1.10, "volume": 100},
        ]
        * 12
    )

    m15 = _build_frame(
        [
            {"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.085, "volume": 100},
            {"open": 1.085, "high": 1.095, "low": 1.08, "close": 1.09, "volume": 100},
            {"open": 1.09, "high": 1.10, "low": 1.085, "close": 1.095, "volume": 100},
            {"open": 1.095, "high": 1.11, "low": 1.09, "close": 1.108, "volume": 100},
        ]
        * 30
    )
    m15.iloc[-1, m15.columns.get_loc("close")] = float(m15["high"].iloc[-13:-1].max()) + 0.01
    m15.iloc[-1, m15.columns.get_loc("high")] = m15.iloc[-1]["close"] + 0.002

    m5 = _build_frame(
        [
            {"open": 1.100, "high": 1.102, "low": 1.098, "close": 1.101, "volume": 100},
            {"open": 1.101, "high": 1.103, "low": 1.099, "close": 1.102, "volume": 120},
            {"open": 1.102, "high": 1.104, "low": 1.100, "close": 1.103, "volume": 110},
            {"open": 1.103, "high": 1.105, "low": 1.094, "close": 1.101, "volume": 130},
            {"open": 1.101, "high": 1.103, "low": 1.099, "close": 1.1005, "volume": 140},
        ]
        * 15
    )
    m5.iloc[-2] = {"open": 1.101, "high": 1.106, "low": 1.092, "close": 1.100, "volume": 220}
    m5.iloc[-1] = {"open": 1.100, "high": 1.102, "low": 1.097, "close": 1.099, "volume": 180}

    snapshot = MarketSnapshot(
        market=Market.FOREX,
        symbol="EURUSD",
        h1=h1,
        m15=m15,
        m5=m5,
        current_price=1.099,
        timestamp=datetime.now(timezone.utc),
    )

    setup = strategy.generate_setup(snapshot)

    assert setup is not None
    assert setup.direction == TradeDirection.LONG
    assert setup.take_profit_1 > setup.entry_price
    assert setup.stop_loss < setup.entry_price
