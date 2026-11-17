"""Verify broker DEMO is never silently simulated and rejects REAL accounts."""
from types import SimpleNamespace
import pytest
from app.config import TradingMode, settings
import app.brokers.mt5_broker as broker_module


@pytest.mark.asyncio
async def test_demo_without_mt5_terminal_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", TradingMode.DEMO)
    monkeypatch.setattr(broker_module, "MT5_AVAILABLE", False)
    broker = broker_module.MT5Broker(paper_mode=False)
    assert broker.paper_mode is False
    assert await broker.connect() is False
    assert broker.is_connected is False


@pytest.mark.asyncio
async def test_demo_rejects_real_account(monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", TradingMode.DEMO)
    monkeypatch.setattr(settings, "MT5_LOGIN", None)
    shutdown_calls = []
    fake = SimpleNamespace(
        ACCOUNT_TRADE_MODE_DEMO=0,
        initialize=lambda **kwargs: True,
        account_info=lambda: SimpleNamespace(
            trade_mode=2, login=123456, balance=3000.0, currency="EUR"
        ),
        shutdown=lambda: shutdown_calls.append(True),
    )
    monkeypatch.setattr(broker_module, "mt5", fake)
    monkeypatch.setattr(broker_module, "MT5_AVAILABLE", True)
    broker = broker_module.MT5Broker(paper_mode=False)
    assert await broker.connect() is False
    assert broker.is_connected is False
    assert shutdown_calls


@pytest.mark.asyncio
async def test_demo_accepts_confirmed_demo_account(monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", TradingMode.DEMO)
    monkeypatch.setattr(settings, "MT5_LOGIN", None)
    fake = SimpleNamespace(
        ACCOUNT_TRADE_MODE_DEMO=0,
        initialize=lambda **kwargs: True,
        account_info=lambda: SimpleNamespace(
            trade_mode=0, login=123456, balance=3000.0, currency="EUR"
        ),
    )
    monkeypatch.setattr(broker_module, "mt5", fake)
    monkeypatch.setattr(broker_module, "MT5_AVAILABLE", True)
    broker = broker_module.MT5Broker(paper_mode=False)
    assert await broker.connect() is True
    assert broker.is_connected is True


@pytest.mark.asyncio
async def test_paper_mode_is_explicit_and_still_available(monkeypatch):
    monkeypatch.setattr(settings, "TRADING_MODE", TradingMode.PAPER)
    monkeypatch.setattr(broker_module, "MT5_AVAILABLE", False)
    broker = broker_module.MT5Broker(paper_mode=True)
    assert await broker.connect() is True
    assert broker.paper_mode is True
