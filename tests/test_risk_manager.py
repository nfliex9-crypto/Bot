import pytest

from app.risk.manager import RiskManager


@pytest.fixture
def rm():
    manager = RiskManager()
    manager._current_balance = 3000.0
    manager._peak_balance = 3000.0
    return manager


def test_risk_per_trade(rm):
    check = rm.check_trade("EURUSD", "long", 1.1000, 1.0950, "forex")
    assert check.approved
    assert abs(check.risk_amount - 22.5) < 0.01  # 3000 * 0.0075


def test_max_drawdown_blocks(rm):
    rm._current_balance = 2500.0  # ~16.7% drawdown from 3000
    check = rm.check_trade("EURUSD", "long", 1.1000, 1.0950, "forex")
    assert not check.approved
    assert "drawdown" in check.reason.lower()


def test_session_limit(rm):
    rm._session_trade_count = 3
    check = rm.check_trade("EURUSD", "long", 1.1000, 1.0950, "forex")
    assert not check.approved
    assert "limit" in check.reason.lower()


def test_duplicate_symbol_blocks(rm):
    rm._open_symbols["EURUSD"] = "long"
    check = rm.check_trade("EURUSD", "long", 1.1000, 1.0950, "forex")
    assert not check.approved


def test_crypto_sizing(rm):
    check = rm.check_trade("BTCUSDT", "long", 50000.0, 49500.0, "crypto")
    assert check.approved
    assert check.position_size > 0
