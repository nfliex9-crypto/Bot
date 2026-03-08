import pandas as pd

from app.risk.engine import RiskEngine


def _candles() -> pd.DataFrame:
    rows = []
    price = 100.0
    for _ in range(50):
        price += 0.2
        rows.append(
            {
                "open": price - 0.3,
                "high": price + 0.5,
                "low": price - 0.7,
                "close": price,
            }
        )
    return pd.DataFrame(rows)


def test_trade_plan_contains_all_targets():
    engine = RiskEngine(0.0075, 0.15, 3, 14)
    plan = engine.build_trade_plan("BUY", 100.0, 100000, _candles())
    assert plan.quantity > 0
    assert plan.stop_loss < 100.0
    assert plan.tp1 < plan.tp2 < plan.tp3


def test_session_limits():
    engine = RiskEngine(0.0075, 0.15, 3, 14)
    ok, _ = engine.can_trade(0, 0.05)
    assert ok

    ok, reason = engine.can_trade(4, 0.05)
    assert not ok
    assert reason == "max_trades_per_session_reached"

    ok, reason = engine.can_trade(1, 0.20)
    assert not ok
    assert reason == "max_drawdown_reached"
