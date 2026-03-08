"""Tests for the risk management engine."""

import pytest
from unittest.mock import patch, MagicMock
from app.risk_engine.position_sizer import PositionSizer
from app.risk_engine.risk_manager import RiskManager, ActiveTradeRisk
from app.strategy.pullback_entry import TradeSetup


class TestPositionSizer:
    def setup_method(self):
        self.sizer = PositionSizer()

    def test_forex_position_basic(self):
        pos = self.sizer.calculate_forex_position(
            account_equity=10000,
            entry_price=1.1000,
            stop_loss_price=1.0950,
            symbol="EURUSD",
        )
        assert pos.lot_size > 0
        assert pos.lot_size >= 0.01
        assert pos.risk_amount > 0
        assert pos.stop_loss_pips == 50.0

    def test_forex_position_jpy_pair(self):
        pos = self.sizer.calculate_forex_position(
            account_equity=10000,
            entry_price=150.000,
            stop_loss_price=149.500,
            symbol="USDJPY",
        )
        assert pos.lot_size > 0
        assert pos.stop_loss_pips == 50.0

    def test_forex_position_zero_sl(self):
        pos = self.sizer.calculate_forex_position(
            account_equity=10000,
            entry_price=1.1000,
            stop_loss_price=1.1000,
            symbol="EURUSD",
        )
        assert pos.lot_size == 0

    def test_crypto_position_basic(self):
        pos = self.sizer.calculate_crypto_position(
            account_equity=10000,
            entry_price=40000,
            stop_loss_price=39000,
            symbol="BTCUSDT",
        )
        assert pos.lot_size > 0
        assert pos.risk_amount > 0

    def test_risk_amount_respects_limit(self):
        pos = self.sizer.calculate_forex_position(
            account_equity=10000,
            entry_price=1.1000,
            stop_loss_price=1.0950,
            symbol="EURUSD",
        )
        assert pos.risk_amount <= 10000 * 0.01


class TestRiskManager:
    def setup_method(self):
        self.rm = RiskManager()
        self.rm.initialize(10000)

    def _make_setup(self, confidence=0.7, direction="long"):
        return TradeSetup(
            direction=direction,
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit_1=1.1075,
            take_profit_2=1.1125,
            take_profit_3=1.1200,
            risk_reward_ratio=2.5,
            confidence=confidence,
            strategy_name="BOS_Pullback_Long",
            timeframe="H1",
            symbol="EURUSD",
        )

    def test_approve_valid_trade(self):
        setup = self._make_setup()
        assessment = self.rm.assess_trade(setup, 10000, "forex")
        assert assessment.approved is True
        assert assessment.position_size is not None
        assert assessment.position_size.lot_size > 0

    def test_reject_low_confidence(self):
        setup = self._make_setup(confidence=0.2)
        assessment = self.rm.assess_trade(setup, 10000, "forex")
        assert assessment.approved is False
        assert "Confidence" in assessment.rejection_reason

    def test_reject_max_drawdown(self):
        self.rm.peak_equity = 10000
        assessment = self.rm.assess_trade(self._make_setup(), 8000, "forex")
        assert assessment.approved is False
        assert "drawdown" in assessment.rejection_reason.lower()

    def test_reject_session_limit(self):
        self.rm.session_trades = 3
        assessment = self.rm.assess_trade(self._make_setup(), 10000, "forex")
        assert assessment.approved is False
        assert "Session" in assessment.rejection_reason

    def test_register_trade(self):
        trade = ActiveTradeRisk(
            order_id="123", symbol="EURUSD", direction="long",
            entry_price=1.1000, stop_loss=1.0950,
            take_profit_1=1.1075, take_profit_2=1.1125,
            take_profit_3=1.1200, lot_size=0.15,
        )
        self.rm.register_trade(trade)
        assert "123" in self.rm.active_trades
        assert self.rm.session_trades == 1

    def test_tp1_hit_triggers_breakeven(self):
        trade = ActiveTradeRisk(
            order_id="456", symbol="EURUSD", direction="long",
            entry_price=1.1000, stop_loss=1.0950,
            take_profit_1=1.1075, take_profit_2=1.1125,
            take_profit_3=1.1200, lot_size=0.15,
        )
        self.rm.register_trade(trade)
        actions = self.rm.check_tp_levels("456", 1.1080)
        assert actions.get("tp1_hit") is True
        assert actions.get("move_to_breakeven") is True
        assert actions.get("new_stop_loss") == 1.1000

    def test_tp2_hit_triggers_trail(self):
        trade = ActiveTradeRisk(
            order_id="789", symbol="EURUSD", direction="long",
            entry_price=1.1000, stop_loss=1.0950,
            take_profit_1=1.1075, take_profit_2=1.1125,
            take_profit_3=1.1200, lot_size=0.15,
            tp1_hit=True,
        )
        self.rm.register_trade(trade)
        actions = self.rm.check_tp_levels("789", 1.1130)
        assert actions.get("tp2_hit") is True
        assert actions.get("trail_stop") is True

    def test_tp3_hit_closes_all(self):
        trade = ActiveTradeRisk(
            order_id="ABC", symbol="EURUSD", direction="long",
            entry_price=1.1000, stop_loss=1.0950,
            take_profit_1=1.1075, take_profit_2=1.1125,
            take_profit_3=1.1200, lot_size=0.15,
            tp1_hit=True, tp2_hit=True,
        )
        self.rm.register_trade(trade)
        actions = self.rm.check_tp_levels("ABC", 1.1210)
        assert actions.get("tp3_hit") is True
        assert actions.get("close_remaining") is True

    def test_short_tp_levels(self):
        trade = ActiveTradeRisk(
            order_id="SHORT1", symbol="EURUSD", direction="short",
            entry_price=1.1000, stop_loss=1.1050,
            take_profit_1=1.0925, take_profit_2=1.0875,
            take_profit_3=1.0800, lot_size=0.15,
        )
        self.rm.register_trade(trade)
        actions = self.rm.check_tp_levels("SHORT1", 1.0920)
        assert actions.get("tp1_hit") is True
        assert actions.get("move_to_breakeven") is True

    def test_reset_session(self):
        self.rm.session_trades = 3
        self.rm.reset_session()
        assert self.rm.session_trades == 0

    def test_get_status(self):
        status = self.rm.get_status(10000)
        assert "active_trades" in status
        assert "current_drawdown" in status
        assert "can_trade" in status
        assert status["can_trade"] is True
