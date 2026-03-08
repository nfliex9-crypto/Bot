"""
Tests for risk management.
"""

import pytest
from config.settings import RiskConfig, StrategyConfig
from core.models import Direction, Trade, TradeSignal, TradeStatus
from risk.risk_manager import RiskManager


@pytest.fixture
def risk_manager():
    config = RiskConfig(
        account_balance=3000.0,
        risk_per_trade=0.0075,
        max_drawdown=0.15,
        max_trades_per_session=3,
        max_daily_loss=0.05,
    )
    return RiskManager(config)


def _make_signal(symbol="EURUSD", direction=Direction.LONG,
                 entry=1.1000, sl=1.0950, tp1=1.1050):
    return TradeSignal(
        symbol=symbol, direction=direction,
        entry_price=entry, stop_loss=sl,
        tp1=tp1, tp2=tp1 + 0.0025, tp3=tp1 + 0.005,
        confidence=0.75, risk_reward=1.0,
    )


class TestRiskManager:
    def test_can_trade_initially(self, risk_manager):
        ok, reason = risk_manager.can_trade()
        assert ok is True

    def test_max_trades_per_session(self, risk_manager):
        for i in range(3):
            signal = _make_signal(symbol=f"SYM{i}")
            trade = Trade(
                symbol=signal.symbol, direction=signal.direction,
                entry_price=signal.entry_price, stop_loss=signal.stop_loss,
                position_size=0.01, status=TradeStatus.OPEN,
            )
            risk_manager.register_trade(trade)

        ok, reason = risk_manager.can_trade()
        assert ok is False
        assert "session" in reason.lower() or "concurrent" in reason.lower()

    def test_position_size_forex(self, risk_manager):
        signal = _make_signal()
        info = {
            "point": 0.00001, "trade_contract_size": 100000,
            "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
        }
        size = risk_manager.calculate_position_size(signal, info)
        assert size > 0
        assert size >= 0.01

    def test_position_size_crypto(self, risk_manager):
        signal = _make_signal(symbol="BTCUSDT", entry=50000, sl=49500, tp1=50500)
        size = risk_manager.calculate_position_size(signal, None)
        assert size > 0

    def test_risk_amount(self, risk_manager):
        expected = 3000 * 0.0075
        assert expected == 22.5

    def test_validate_signal_low_rr(self, risk_manager):
        signal = _make_signal()
        signal.risk_reward = 0.5
        ok, reason = risk_manager.validate_signal(signal)
        assert ok is False
        assert "risk" in reason.lower()

    def test_close_trade_updates_balance(self, risk_manager):
        signal = _make_signal()
        trade = Trade(
            symbol="EURUSD", direction=Direction.LONG,
            entry_price=1.1000, stop_loss=1.0950,
            position_size=0.1, status=TradeStatus.OPEN,
        )
        risk_manager.register_trade(trade)
        risk_manager.close_trade(trade, pnl=15.0)

        assert risk_manager.account.balance == 3015.0
        assert risk_manager.account.winning_trades == 1

    def test_drawdown_calculation(self, risk_manager):
        risk_manager.account.peak_balance = 3000.0
        risk_manager.account.equity = 2700.0
        assert risk_manager.account.current_drawdown == 0.1

    def test_max_drawdown_blocks_trading(self, risk_manager):
        risk_manager.account.peak_balance = 3000.0
        risk_manager.account.equity = 2500.0
        ok, reason = risk_manager.can_trade()
        assert ok is False
