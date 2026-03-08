"""
Tests for trade management: TP levels, breakeven, partial closes.
"""

import pytest
from config.settings import StrategyConfig
from core.models import Direction, Trade, TradeStatus
from trade_management.manager import TradeManager


@pytest.fixture
def trade_manager():
    return TradeManager(StrategyConfig())


def _long_trade():
    return Trade(
        symbol="EURUSD", direction=Direction.LONG,
        entry_price=1.1000, stop_loss=1.0950,
        tp1=1.1050, tp2=1.1075, tp3=1.1100,
        position_size=0.10, status=TradeStatus.OPEN,
    )


def _short_trade():
    return Trade(
        symbol="GBPUSD", direction=Direction.SHORT,
        entry_price=1.2500, stop_loss=1.2550,
        tp1=1.2450, tp2=1.2425, tp3=1.2400,
        position_size=0.10, status=TradeStatus.OPEN,
    )


class TestTradeManager:
    def test_no_action_within_range(self, trade_manager):
        trade = _long_trade()
        actions = trade_manager.check_trade(trade, 1.1020)
        assert len(actions) == 0

    def test_tp1_hit_long(self, trade_manager):
        trade = _long_trade()
        actions = trade_manager.check_trade(trade, 1.1055)
        tp_actions = [a for a in actions if a.get("reason") == "tp1"]
        assert len(tp_actions) == 1
        assert trade.tp1_hit is True
        assert trade.breakeven_set is True
        assert trade.stop_loss == trade.entry_price

    def test_tp2_hit_long(self, trade_manager):
        trade = _long_trade()
        trade_manager.check_trade(trade, 1.1055)  # hit TP1 first
        actions = trade_manager.check_trade(trade, 1.1080)
        tp2_actions = [a for a in actions if a.get("reason") == "tp2"]
        assert len(tp2_actions) == 1

    def test_tp3_hit_closes_full(self, trade_manager):
        trade = _long_trade()
        trade_manager.check_trade(trade, 1.1055)
        trade_manager.check_trade(trade, 1.1080)
        actions = trade_manager.check_trade(trade, 1.1105)
        tp3_actions = [a for a in actions if a.get("reason") == "tp3"]
        assert len(tp3_actions) == 1
        assert tp3_actions[0]["action"] == "close_full"

    def test_sl_hit_long(self, trade_manager):
        trade = _long_trade()
        actions = trade_manager.check_trade(trade, 1.0945)
        assert any(a["reason"] == "stop_loss" for a in actions)

    def test_sl_hit_short(self, trade_manager):
        trade = _short_trade()
        actions = trade_manager.check_trade(trade, 1.2555)
        assert any(a["reason"] == "stop_loss" for a in actions)

    def test_tp1_hit_short(self, trade_manager):
        trade = _short_trade()
        actions = trade_manager.check_trade(trade, 1.2445)
        assert trade.tp1_hit is True
        assert trade.stop_loss == trade.entry_price

    def test_breakeven_protects_entry(self, trade_manager):
        trade = _long_trade()
        trade_manager.check_trade(trade, 1.1055)
        assert trade.stop_loss == 1.1000
        actions = trade_manager.check_trade(trade, 1.1000)
        assert any(a["reason"] == "stop_loss" for a in actions)

    def test_unrealized_pnl(self, trade_manager):
        trade = _long_trade()
        trade.current_price = 1.1020
        pnl = trade_manager.get_unrealized_pnl([trade])
        assert pnl > 0
