"""Tests for market data connectors (simulation mode)."""
import pytest
import asyncio
import pandas as pd

from src.connectors.mt5_connector import MT5Connector
from src.connectors.binance_connector import BinanceConnector


@pytest.fixture
async def mt5():
    conn = MT5Connector()
    await conn.connect()
    return conn


@pytest.fixture
async def binance():
    conn = BinanceConnector()
    await conn.connect()
    return conn


@pytest.mark.asyncio
async def test_mt5_sim_ohlcv():
    conn = MT5Connector()
    await conn.connect()
    df = await conn.get_ohlcv("EURUSD", "H1", count=100)
    assert not df.empty
    assert len(df) == 100
    assert set(["open", "high", "low", "close", "volume"]).issubset(df.columns)


@pytest.mark.asyncio
async def test_mt5_sim_tick():
    conn = MT5Connector()
    await conn.connect()
    tick = await conn.get_tick("EURUSD")
    assert tick is not None
    assert tick.bid > 0
    assert tick.ask > tick.bid


@pytest.mark.asyncio
async def test_mt5_sim_account():
    conn = MT5Connector()
    await conn.connect()
    account = await conn.get_account_info()
    assert account is not None
    assert account.balance > 0


@pytest.mark.asyncio
async def test_binance_sim_ohlcv():
    conn = BinanceConnector()
    await conn.connect()
    df = await conn.get_ohlcv("BTCUSDT", "H1", count=100)
    assert not df.empty
    assert len(df) == 100
    assert "close" in df.columns
    assert (df["close"] > 0).all()


@pytest.mark.asyncio
async def test_binance_sim_tick():
    conn = BinanceConnector()
    await conn.connect()
    tick = await conn.get_tick("ETHUSDT")
    assert tick is not None
    assert tick.last > 0


@pytest.mark.asyncio
async def test_ohlcv_hloc_validity():
    conn = MT5Connector()
    await conn.connect()
    df = await conn.get_ohlcv("GBPUSD", "M5", count=50)
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df["open"]).all()
    assert (df["high"] >= df["close"]).all()
    assert (df["low"] <= df["open"]).all()
    assert (df["low"] <= df["close"]).all()
