from datetime import datetime, timezone

from app.risk.manager import RiskManager, RiskProfile


def test_position_size_uses_075_percent_risk() -> None:
    manager = RiskManager(
        RiskProfile(
            account_balance=3000,
            risk_per_trade_pct=0.75,
            max_drawdown_pct=15,
            max_trades_per_session=3,
        )
    )
    size = manager.position_size(entry_price=1.2000, stop_loss=1.1970)
    assert round(size, 2) == 7500.00


def test_max_trades_per_session_guard() -> None:
    manager = RiskManager(
        RiskProfile(
            account_balance=3000,
            risk_per_trade_pct=0.75,
            max_drawdown_pct=15,
            max_trades_per_session=3,
        )
    )
    now = datetime.now(tz=timezone.utc)
    assert manager.can_open_trade(now) is True
    manager.mark_trade_opened(now)
    manager.mark_trade_opened(now)
    manager.mark_trade_opened(now)
    assert manager.can_open_trade(now) is False
