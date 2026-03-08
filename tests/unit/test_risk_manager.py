"""Tests for the risk management system."""
import pytest
from src.risk.risk_manager import RiskManager
from config.settings import settings


@pytest.fixture
def risk_manager():
    rm = RiskManager()
    rm.update_balance(3000.0)
    return rm


def test_pre_trade_check_passes_initially(risk_manager):
    check = risk_manager.pre_trade_check()
    assert check.approved is True
    assert check.rejection_reason is None


def test_max_trades_per_session_blocks(risk_manager):
    for _ in range(settings.max_trades_per_session):
        risk_manager.record_trade_open(22.5)
    check = risk_manager.pre_trade_check()
    assert check.approved is False
    assert "Max trades" in check.rejection_reason


def test_max_drawdown_blocks(risk_manager):
    # Simulate large losses
    risk_manager.update_balance(3000.0 * (1 - settings.max_drawdown_pct - 0.01))
    check = risk_manager.pre_trade_check()
    assert check.approved is False
    assert "drawdown" in check.rejection_reason.lower()


def test_position_size_forex(risk_manager):
    pos = risk_manager.calculate_position_size_forex(
        symbol="EURUSD",
        entry=1.1000,
        stop_loss=1.0950,
    )
    assert pos.valid is True
    assert pos.lot_size >= 0.01
    assert pos.risk_amount == pytest.approx(3000.0 * 0.0075, rel=0.01)


def test_position_size_crypto(risk_manager):
    pos = risk_manager.calculate_position_size_crypto(
        symbol="BTCUSDT",
        entry=50000.0,
        stop_loss=49000.0,
    )
    assert pos.valid is True
    assert pos.lot_size > 0
    assert pos.risk_amount == pytest.approx(3000.0 * 0.0075, rel=0.01)


def test_position_size_zero_stop_distance(risk_manager):
    pos = risk_manager.calculate_position_size_forex(
        symbol="EURUSD",
        entry=1.1000,
        stop_loss=1.1000,
    )
    assert pos.valid is False


def test_take_profits_bullish():
    tp1, tp2, tp3 = RiskManager.calculate_take_profits(1.1000, 1.0950, "bullish")
    risk = 1.1000 - 1.0950
    assert tp1 == pytest.approx(1.1000 + risk * 1.0, rel=1e-6)
    assert tp2 == pytest.approx(1.1000 + risk * 1.5, rel=1e-6)
    assert tp3 == pytest.approx(1.1000 + risk * 2.0, rel=1e-6)


def test_take_profits_bearish():
    tp1, tp2, tp3 = RiskManager.calculate_take_profits(1.1000, 1.1050, "bearish")
    risk = 1.1050 - 1.1000
    assert tp1 == pytest.approx(1.1000 - risk * 1.0, rel=1e-6)
    assert tp2 == pytest.approx(1.1000 - risk * 1.5, rel=1e-6)


def test_break_even_bullish():
    be = RiskManager.calculate_break_even(1.1000, 1.1050, "bullish")
    assert be > 1.1000


def test_break_even_bearish():
    be = RiskManager.calculate_break_even(1.1000, 1.0950, "bearish")
    assert be < 1.1000


def test_drawdown_calculation(risk_manager):
    risk_manager._peak_balance = 3000.0
    risk_manager._current_balance = 2700.0
    dd = risk_manager.current_drawdown_pct
    assert dd == pytest.approx(0.10, rel=0.01)


def test_session_reset(risk_manager):
    risk_manager.record_trade_open(22.5)
    risk_manager.record_trade_open(22.5)
    assert risk_manager.session_trades == 2
    risk_manager.reset_session()
    assert risk_manager.session_trades == 0
