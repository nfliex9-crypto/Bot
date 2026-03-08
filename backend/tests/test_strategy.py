import pandas as pd

from app.db.models import MarketType, OrderSide
from app.services.strategy import SmartMoneyStrategy


def test_strategy_detects_bullish_smart_money_setup() -> None:
    rows = []
    price = 100.0
    for index in range(59):
        open_price = price
        close_price = price + 0.2
        high = close_price + 0.5
        low = open_price - 0.5
        volume = 1000 + index * 10
        rows.append(
            {
                "time": pd.Timestamp("2024-01-01") + pd.Timedelta(minutes=15 * index),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": volume,
            }
        )
        price = close_price

    rows.append(
        {
            "time": pd.Timestamp("2024-01-01") + pd.Timedelta(minutes=15 * 59),
            "open": price - 0.3,
            "high": price + 5.0,
            "low": 99.0,
            "close": price + 4.0,
            "volume": 4000,
        }
    )

    df = pd.DataFrame(rows)
    strategy = SmartMoneyStrategy()

    signal = strategy.analyze("BTCUSDT", MarketType.CRYPTO, "M15", df)

    assert signal is not None
    assert signal.side == OrderSide.LONG
    assert signal.stop_loss < signal.entry_price
    assert signal.tp3 > signal.tp2 > signal.tp1 > signal.entry_price
