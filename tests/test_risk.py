from __future__ import annotations

from app.core.config import Settings
from app.services.risk import RiskManager


def test_position_size_respects_trade_risk() -> None:
    settings = Settings(account_balance=3000.0, risk_per_trade=0.0075)
    manager = RiskManager(settings)

    size = manager.position_size(equity=3000.0, entry_price=1.1000, stop_loss=1.0950)

    assert round(manager.risk_amount(3000.0), 2) == 22.50
    assert round(size, 4) == 4500.0


def test_drawdown_limit_blocks_trading() -> None:
    settings = Settings(max_drawdown=0.15)
    manager = RiskManager(settings)

    result = manager.validate_drawdown(equity=2500.0, peak_equity=3000.0)

    assert result.allowed is False
    assert result.reason == "max_drawdown_reached"
