"""
Tests for paper trading executor.
"""

import pytest
import asyncio
from core.models import Direction, TradeSignal, TradeStatus
from execution.paper_executor import PaperExecutor


@pytest.fixture
def executor():
    return PaperExecutor()


@pytest.mark.asyncio
async def test_place_order(executor):
    signal = TradeSignal(
        symbol="EURUSD", direction=Direction.LONG,
        entry_price=1.1000, stop_loss=1.0950,
        tp1=1.1050, tp2=1.1075, tp3=1.1100,
    )
    trade = await executor.place_order(signal, 0.10)
    assert trade is not None
    assert trade.status == TradeStatus.OPEN
    assert trade.entry_price == 1.1000
    assert trade.market == "paper"


@pytest.mark.asyncio
async def test_close_position(executor):
    signal = TradeSignal(
        symbol="BTCUSDT", direction=Direction.SHORT,
        entry_price=50000, stop_loss=51000,
        tp1=49000, tp2=48500, tp3=48000,
    )
    trade = await executor.place_order(signal, 0.01)
    trade.current_price = 49000
    success = await executor.close_position(trade)
    assert success is True


@pytest.mark.asyncio
async def test_modify_sl(executor):
    signal = TradeSignal(
        symbol="EURUSD", direction=Direction.LONG,
        entry_price=1.1000, stop_loss=1.0950,
        tp1=1.1050, tp2=1.1075, tp3=1.1100,
    )
    trade = await executor.place_order(signal, 0.10)
    success = await executor.modify_sl(trade, 1.1000)
    assert success is True
