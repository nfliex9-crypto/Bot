from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.core.config import Settings
from app.domain.models import MarketType, TradeSide
from app.strategy.liquidity import LiquiditySweepStrategy


def _frame_from_rows(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    start = datetime(2026, 3, 1, tzinfo=UTC)
    return pd.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=index * 5) for index in range(len(rows))],
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
            "volume": [1000.0] * len(rows),
        }
    )


def test_liquidity_sweep_strategy_generates_long_signal() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    strategy = LiquiditySweepStrategy(settings)

    h1_rows = []
    price = 1.1000
    for _ in range(40):
        h1_rows.append((price, price + 0.0020, price - 0.0010, price + 0.0015))
        price += 0.0007

    m15_rows = []
    price = 1.1180
    for _ in range(24):
        m15_rows.append((price, price + 0.0011, price - 0.0008, price + 0.0004))
        price += 0.00015
    m15_rows.append((1.1215, 1.1220, 1.1168, 1.1208))  # sweep below prior lows and reclaim
    m15_rows.extend(
        [
            (1.1208, 1.1224, 1.1201, 1.1219),
            (1.1219, 1.1234, 1.1215, 1.1230),
            (1.1230, 1.1238, 1.1223, 1.1235),
            (1.1235, 1.1240, 1.1229, 1.1236),
            (1.1236, 1.1242, 1.1231, 1.1240),
        ]
    )

    m5_rows = []
    price = 1.1210
    for _ in range(16):
        m5_rows.append((price, price + 0.0006, price - 0.0004, price + 0.0003))
        price += 0.00008
    m5_rows.extend(
        [
            (1.1230, 1.1233, 1.1221, 1.1226),
            (1.1226, 1.1229, 1.1219, 1.1224),
            (1.1224, 1.1230, 1.1220, 1.1228),
            (1.1228, 1.1234, 1.1225, 1.1232),
            (1.1232, 1.1238, 1.1227, 1.1236),
        ]
    )

    signal = strategy.generate_signal(
        symbol="EURUSD",
        market=MarketType.FOREX,
        h1_frame=_frame_from_rows(h1_rows),
        m15_frame=_frame_from_rows(m15_rows),
        m5_frame=_frame_from_rows(m5_rows),
    )

    assert signal is not None
    assert signal.side == TradeSide.BUY
    assert signal.stop_loss < signal.entry
    assert signal.take_profit_1 > signal.entry
    assert signal.confidence >= 0.55
