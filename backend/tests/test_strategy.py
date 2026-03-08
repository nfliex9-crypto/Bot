import pandas as pd

from app.strategy.detector import SmartMoneyStrategy


def _frame() -> pd.DataFrame:
    rows = []
    p = 100.0
    for i in range(70):
        p += 0.1
        rows.append(
            {
                "open": p - 0.2,
                "high": p + 0.5,
                "low": p - 0.4,
                "close": p,
                "volume": 500 + i,
            }
        )

    rows[-1]["high"] = max(r["high"] for r in rows[:-1]) + 0.8
    rows[-1]["close"] = rows[-1]["open"] - 0.2

    return pd.DataFrame(rows)


def test_strategy_returns_signal_or_none():
    strat = SmartMoneyStrategy()
    signal = strat.generate_signal("FOREX", "EURUSD", _frame())
    assert signal is None or signal.side in {"BUY", "SELL"}
