"""Tests for the paper executor."""
from __future__ import annotations

import pytest

from core.enums import Direction, Market, TradeStatus
from core.models import TradeRecord
from execution.paper_executor import PaperExecutor


def _make_trade() -> TradeRecord:
    return TradeRecord(
        signal_id="test-signal-123",
        symbol="EURUSD",
        market=Market.FOREX,
        direction=Direction.LONG,
        status=TradeStatus.OPEN,
        entry_price=1.1000,
        stop_loss=1.0960,
        tp1=1.1040,
        tp2=1.1060,
        tp3=1.1080,
        position_size=0.10,
        risk_amount=22.50,
    )


class TestPaperExecutor:

    @pytest.mark.asyncio
    async def test_open_trade(self):
        ex = PaperExecutor()
        trade = _make_trade()
        order_id = await ex.open_trade(trade)
        assert order_id is not None
        assert order_id.startswith("PAPER-")

    @pytest.mark.asyncio
    async def test_close_trade(self):
        ex = PaperExecutor()
        trade = _make_trade()
        result = await ex.close_trade(trade, "test_close")
        assert result is True

    @pytest.mark.asyncio
    async def test_partial_close(self):
        ex = PaperExecutor()
        trade = _make_trade()
        original_size = trade.position_size
        result = await ex.partial_close(trade, 0.33)
        assert result is True
        assert trade.position_size < original_size

    @pytest.mark.asyncio
    async def test_modify_sl(self):
        ex = PaperExecutor()
        trade = _make_trade()
        result = await ex.modify_sl(trade, 1.1000)
        assert result is True
        assert trade.stop_loss == 1.1000

    @pytest.mark.asyncio
    async def test_open_pnl_long(self):
        ex = PaperExecutor()
        trade = _make_trade()
        pnl = await ex.get_open_pnl(trade, 1.1050)
        assert pnl > 0

    @pytest.mark.asyncio
    async def test_open_pnl_loss(self):
        ex = PaperExecutor()
        trade = _make_trade()
        pnl = await ex.get_open_pnl(trade, 1.0950)
        assert pnl < 0
