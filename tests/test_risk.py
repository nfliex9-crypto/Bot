from __future__ import annotations

from app.core.config import Settings
from app.domain.models import AccountSnapshot, MarketType, TradeSide, TradeSignal, TradingMode, default_symbol_specs
from app.risk.manager import RiskManager


def test_risk_manager_sizes_trade_from_account_risk() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    manager = RiskManager(settings)
    account = AccountSnapshot(balance=3000.0, equity=3000.0, peak_balance=3000.0, session_trade_count=0)
    signal = TradeSignal(
        symbol="EURUSD",
        market=MarketType.FOREX,
        side=TradeSide.BUY,
        entry=1.1050,
        stop_loss=1.1040,
        take_profit_1=1.1060,
        take_profit_2=1.1065,
        take_profit_3=1.1070,
        confidence=0.72,
        stop_method="atr",
    )
    sized = manager.size_trade(signal, account, default_symbol_specs()["EURUSD"])

    assert sized.risk_amount == 22.5
    assert round(sized.position_size, 2) == 0.22


def test_risk_manager_blocks_after_drawdown_or_trade_limit() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    manager = RiskManager(settings)

    drawdown_block = manager.can_open_trade(
        AccountSnapshot(balance=2550.0, equity=2550.0, peak_balance=3000.0, session_trade_count=0)
    )
    session_block = manager.can_open_trade(
        AccountSnapshot(balance=3000.0, equity=3000.0, peak_balance=3000.0, session_trade_count=3)
    )

    assert not drawdown_block.allowed
    assert "drawdown" in drawdown_block.reason.lower()
    assert not session_block.allowed
    assert "session" in session_block.reason.lower()
