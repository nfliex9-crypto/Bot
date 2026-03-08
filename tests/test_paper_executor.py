import pytest
import asyncio

from app.execution.paper_executor import PaperExecutor


@pytest.fixture
def executor():
    return PaperExecutor()


@pytest.mark.asyncio
async def test_place_order(executor):
    result = await executor.place_market_order("EURUSD", "long", 0.1, 1.0950, 1.1050)
    assert result.success
    assert result.order_id


@pytest.mark.asyncio
async def test_close_position(executor):
    await executor.place_market_order("EURUSD", "long", 0.1)
    result = await executor.close_position("EURUSD", "long", 0.1)
    assert result.success


@pytest.mark.asyncio
async def test_modify_sl(executor):
    await executor.place_market_order("EURUSD", "long", 0.1, 1.0950)
    result = await executor.modify_stop_loss("EURUSD", "test-id", 1.1000)
    assert result.success
    assert executor._positions["EURUSD"]["stop_loss"] == 1.1000


@pytest.mark.asyncio
async def test_balance_update(executor):
    initial = executor._balance
    executor.update_balance(100.0)
    assert executor._balance == initial + 100.0


@pytest.mark.asyncio
async def test_get_balance(executor):
    balance = await executor.get_account_balance()
    assert balance == 3000.0
