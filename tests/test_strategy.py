from __future__ import annotations

import pandas as pd

from trading_bot.domain import MarketType, TradeDirection
from trading_bot.strategy import calculate_atr, detect_execution_setup, determine_h1_bias


def make_frame(rows: list[dict[str, float]], freq: str = "5min") -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, index=index)


def test_calculate_atr_returns_positive_value() -> None:
    frame = make_frame(
        [
            {"open": 1.10, "high": 1.11, "low": 1.09, "close": 1.105, "volume": 1000},
            {"open": 1.105, "high": 1.115, "low": 1.10, "close": 1.112, "volume": 1000},
            {"open": 1.112, "high": 1.118, "low": 1.108, "close": 1.117, "volume": 1000},
            {"open": 1.117, "high": 1.121, "low": 1.111, "close": 1.119, "volume": 1000},
            {"open": 1.119, "high": 1.123, "low": 1.115, "close": 1.122, "volume": 1000},
            {"open": 1.122, "high": 1.126, "low": 1.118, "close": 1.124, "volume": 1000},
            {"open": 1.124, "high": 1.129, "low": 1.121, "close": 1.128, "volume": 1000},
            {"open": 1.128, "high": 1.132, "low": 1.125, "close": 1.131, "volume": 1000},
            {"open": 1.131, "high": 1.136, "low": 1.127, "close": 1.134, "volume": 1000},
            {"open": 1.134, "high": 1.138, "low": 1.130, "close": 1.137, "volume": 1000},
            {"open": 1.137, "high": 1.140, "low": 1.133, "close": 1.139, "volume": 1000},
            {"open": 1.139, "high": 1.143, "low": 1.136, "close": 1.142, "volume": 1000},
            {"open": 1.142, "high": 1.146, "low": 1.139, "close": 1.145, "volume": 1000},
            {"open": 1.145, "high": 1.149, "low": 1.141, "close": 1.147, "volume": 1000},
            {"open": 1.147, "high": 1.151, "low": 1.144, "close": 1.149, "volume": 1000},
        ]
    )
    assert calculate_atr(frame) > 0


def test_determine_h1_bias_identifies_bullish_structure() -> None:
    rows = []
    price = 1.10
    for _ in range(80):
        rows.append(
            {
                "open": price,
                "high": price + 0.006,
                "low": price - 0.003,
                "close": price + 0.004,
                "volume": 1000,
            }
        )
        price += 0.002
    frame = make_frame(rows, freq="1h")
    assert determine_h1_bias(frame) == "bullish"


def test_detect_execution_setup_returns_long_signal() -> None:
    h1_rows = []
    price = 100.0
    for _ in range(120):
        h1_rows.append(
            {
                "open": price,
                "high": price + 1.2,
                "low": price - 0.4,
                "close": price + 0.8,
                "volume": 1000,
            }
        )
        price += 0.35
    h1 = make_frame(h1_rows, freq="1h")

    m15_rows = []
    price = 140.0
    for _ in range(80):
        m15_rows.append(
            {
                "open": price,
                "high": price + 0.8,
                "low": price - 0.3,
                "close": price + 0.5,
                "volume": 1000,
            }
        )
        price += 0.2
    m15 = make_frame(m15_rows, freq="15min")

    m5_rows = []
    base = 150.0
    for idx in range(30):
        close = base + (idx * 0.18)
        m5_rows.append(
            {
                "open": close - 0.10,
                "high": close + 0.25,
                "low": close - 0.22,
                "close": close,
                "volume": 1000,
            }
        )

    m5_rows.extend(
        [
            {"open": 155.3, "high": 155.5, "low": 153.0, "close": 154.9, "volume": 1000},
            {"open": 154.9, "high": 155.2, "low": 154.7, "close": 155.0, "volume": 1000},
            {"open": 155.0, "high": 156.4, "low": 154.9, "close": 156.2, "volume": 1000},
            {"open": 156.15, "high": 156.6, "low": 155.8, "close": 156.4, "volume": 1000},
            {"open": 156.4, "high": 156.7, "low": 156.0, "close": 156.55, "volume": 1000},
            {"open": 156.55, "high": 156.8, "low": 155.7, "close": 156.1, "volume": 1000},
            {"open": 156.1, "high": 156.3, "low": 155.2, "close": 155.7, "volume": 1000},
            {"open": 155.7, "high": 155.9, "low": 154.95, "close": 155.55, "volume": 1000},
            {"open": 155.55, "high": 155.75, "low": 154.75, "close": 155.48, "volume": 1000},
            {"open": 155.48, "high": 155.85, "low": 154.65, "close": 155.6, "volume": 1000},
        ]
    )
    m5 = make_frame(m5_rows, freq="5min")

    snapshot, signal = detect_execution_setup(
        symbol="BTCUSDT",
        market=MarketType.CRYPTO,
        h1_frame=h1,
        m15_frame=m15,
        m5_frame=m5,
        session="london",
    )

    assert snapshot.h1_bias == "bullish"
    assert snapshot.m15_structure == "bullish"
    assert signal is not None
    assert signal.direction == TradeDirection.LONG
    assert signal.entry_price > signal.stop_loss
    assert len(signal.take_profit_levels) == 3
