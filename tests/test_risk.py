"""Tests for risk management."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from config.settings import settings
from core.enums import Direction, Market, SignalType
from core.models import TradeRecord, TradeSignal
from database.repository import TradeRepository
from risk.manager import RiskManager


@pytest.fixture
def mock_repo():
    repo = TradeRepository()
    repo.get_session_trade_count = AsyncMock(return_value=0)
    repo.get_open_trades = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def risk_mgr(mock_repo):
    return RiskManager(mock_repo)


def _make_signal(direction=Direction.LONG, entry=1.1000, sl=1.0960, tp_mult=1.0) -> TradeSignal:
    risk = abs(entry - sl)
    return TradeSignal(
        symbol="EURUSD",
        market=Market.FOREX,
        direction=direction,
        signal_type=SignalType.PULLBACK_ENTRY,
        entry_price=entry,
        stop_loss=sl,
        tp1=entry + risk * settings.tp1_ratio if direction == Direction.LONG else entry - risk * settings.tp1_ratio,
        tp2=entry + risk * settings.tp2_ratio if direction == Direction.LONG else entry - risk * settings.tp2_ratio,
        tp3=entry + risk * settings.tp3_ratio if direction == Direction.LONG else entry - risk * settings.tp3_ratio,
        risk_reward=1.5,
    )


class TestRiskManager:

    @pytest.mark.asyncio
    async def test_can_trade_initially(self, risk_mgr):
        ok, reason = await risk_mgr.can_trade()
        assert ok is True

    @pytest.mark.asyncio
    async def test_max_drawdown_blocks(self, risk_mgr):
        risk_mgr.account.current_drawdown_pct = 16.0
        ok, reason = await risk_mgr.can_trade()
        assert ok is False
        assert "drawdown" in reason.lower()

    def test_validate_valid_long(self, risk_mgr):
        signal = _make_signal()
        valid, reason = risk_mgr.validate_signal(signal)
        assert valid is True

    def test_validate_invalid_sl(self, risk_mgr):
        signal = _make_signal(sl=1.1050)
        valid, reason = risk_mgr.validate_signal(signal)
        assert valid is False

    def test_position_sizing_forex(self, risk_mgr):
        signal = _make_signal()
        size = risk_mgr.calculate_position_size(signal, Market.FOREX)
        assert size > 0
        assert size <= 10.0

    def test_position_sizing_crypto(self, risk_mgr):
        signal = _make_signal(entry=50000, sl=49000)
        signal.market = Market.CRYPTO
        size = risk_mgr.calculate_position_size(signal, Market.CRYPTO)
        assert size > 0

    def test_breakeven_check_long(self, risk_mgr):
        signal = _make_signal()
        trade = risk_mgr.create_trade_record(signal, 0.10)
        be = risk_mgr.check_breakeven(trade, trade.tp1 + 0.001)
        assert be == trade.entry_price

    def test_breakeven_not_triggered(self, risk_mgr):
        signal = _make_signal()
        trade = risk_mgr.create_trade_record(signal, 0.10)
        be = risk_mgr.check_breakeven(trade, trade.entry_price)
        assert be is None

    def test_stop_loss_hit_long(self, risk_mgr):
        signal = _make_signal()
        trade = risk_mgr.create_trade_record(signal, 0.10)
        assert risk_mgr.check_stop_loss(trade, trade.stop_loss - 0.0001) is True
        assert risk_mgr.check_stop_loss(trade, trade.entry_price) is False

    def test_tp_hits(self, risk_mgr):
        signal = _make_signal()
        trade = risk_mgr.create_trade_record(signal, 0.10)
        hits = risk_mgr.check_tp_hits(trade, trade.tp3 + 0.001)
        assert "tp1" in hits
        assert "tp2" in hits
        assert "tp3" in hits

    def test_account_pnl_update(self, risk_mgr):
        signal = _make_signal()
        trade = risk_mgr.create_trade_record(signal, 0.10)
        trade.pnl = 22.50
        risk_mgr.update_account_pnl(trade)
        assert risk_mgr.account.balance == settings.account_balance + 22.50
        assert risk_mgr.account.winning_trades == 1
