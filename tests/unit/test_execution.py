"""Tests for paper trading execution engines."""
import pytest
import asyncio
from src.execution.mt5_executor import MT5Executor
from src.execution.binance_executor import BinanceExecutor


@pytest.fixture
def mt5_paper():
    return MT5Executor(paper_mode=True)


@pytest.fixture
def binance_paper():
    return BinanceExecutor(paper_mode=True)


@pytest.mark.asyncio
async def test_mt5_paper_open_trade(mt5_paper):
    result = await mt5_paper.open_trade(
        symbol="EURUSD",
        direction="long",
        lot_size=0.1,
        entry_price=1.1000,
        stop_loss=1.0950,
        tp1=1.1050,
    )
    assert result.success is True
    assert result.broker_ticket is not None
    assert result.executed_price == 1.1000


@pytest.mark.asyncio
async def test_mt5_paper_close_trade(mt5_paper):
    open_result = await mt5_paper.open_trade(
        symbol="EURUSD", direction="long", lot_size=0.1,
        entry_price=1.1000, stop_loss=1.0950, tp1=1.1050,
    )
    close_result = await mt5_paper.close_trade(
        broker_ticket=open_result.broker_ticket,
        symbol="EURUSD",
        lot_size=0.1,
        direction="long",
        close_price=1.1050,
    )
    assert close_result.success is True
    assert close_result.pnl == pytest.approx(50.0, abs=5.0)


@pytest.mark.asyncio
async def test_mt5_paper_modify_sl(mt5_paper):
    open_result = await mt5_paper.open_trade(
        symbol="GBPUSD", direction="long", lot_size=0.1,
        entry_price=1.2500, stop_loss=1.2450, tp1=1.2550,
    )
    success = await mt5_paper.modify_stop_loss(
        broker_ticket=open_result.broker_ticket,
        symbol="GBPUSD",
        new_stop_loss=1.2500,
    )
    assert success is True


@pytest.mark.asyncio
async def test_mt5_paper_get_positions(mt5_paper):
    await mt5_paper.open_trade(
        symbol="USDJPY", direction="short", lot_size=0.05,
        entry_price=150.00, stop_loss=150.50, tp1=149.50,
    )
    positions = await mt5_paper.get_open_positions()
    assert len(positions) >= 1
    symbols = [p["symbol"] for p in positions]
    assert "USDJPY" in symbols


@pytest.mark.asyncio
async def test_binance_paper_open_trade(binance_paper):
    result = await binance_paper.open_trade(
        symbol="BTCUSDT",
        direction="long",
        lot_size=0.001,
        entry_price=50000.0,
        stop_loss=49000.0,
        tp1=51000.0,
    )
    assert result.success is True
    assert result.broker_ticket is not None


@pytest.mark.asyncio
async def test_binance_paper_close_trade_pnl(binance_paper):
    open_result = await binance_paper.open_trade(
        symbol="ETHUSDT", direction="long", lot_size=0.01,
        entry_price=3000.0, stop_loss=2950.0, tp1=3050.0,
    )
    close_result = await binance_paper.close_trade(
        broker_ticket=open_result.broker_ticket,
        symbol="ETHUSDT",
        lot_size=0.01,
        direction="long",
        close_price=3050.0,
    )
    assert close_result.success is True
    assert close_result.pnl == pytest.approx(0.5, abs=0.01)


@pytest.mark.asyncio
async def test_binance_paper_short_pnl(binance_paper):
    open_result = await binance_paper.open_trade(
        symbol="SOLUSDT", direction="short", lot_size=1.0,
        entry_price=100.0, stop_loss=105.0, tp1=95.0,
    )
    close_result = await binance_paper.close_trade(
        broker_ticket=open_result.broker_ticket,
        symbol="SOLUSDT",
        lot_size=1.0,
        direction="short",
        close_price=95.0,
    )
    assert close_result.success is True
    assert close_result.pnl == pytest.approx(5.0, abs=0.1)
