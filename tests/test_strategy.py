import pandas as pd

from app.strategy.market_structure import calculate_atr, detect_break_of_structure


def _frame() -> pd.DataFrame:
    values = []
    price = 100.0
    for i in range(60):
        price += 0.2
        values.append(
            {
                "open": price - 0.1,
                "high": price + 0.3,
                "low": price - 0.3,
                "close": price,
                "volume": 1000 + i,
            }
        )
    return pd.DataFrame(values)


def test_atr_positive() -> None:
    frame = _frame()
    atr = calculate_atr(frame, period=14)
    assert atr > 0


def test_break_of_structure_bullish_true() -> None:
    frame = _frame()
    frame.loc[frame.index[-1], "close"] = frame["high"].iloc[-2] + 0.2
    assert detect_break_of_structure(frame, direction="bullish", lookback=10) is True
