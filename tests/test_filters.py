"""Tests for session and news filters."""
from __future__ import annotations

from datetime import datetime

import pytest

from core.enums import SessionName
from filters.news_filter import NewsFilter
from filters.session_filter import SessionFilter


class TestSessionFilter:

    def test_london_session(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 2, 10, 0)  # Monday 10:00 UTC
        session = sf.get_session(dt)
        assert session == SessionName.LONDON

    def test_newyork_session(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 2, 18, 0)  # Monday 18:00 UTC
        session = sf.get_session(dt)
        assert session == SessionName.NEW_YORK

    def test_overlap_session(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 2, 14, 0)  # Monday 14:00 UTC
        session = sf.get_session(dt)
        assert session == SessionName.OVERLAP

    def test_closed_session(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 2, 3, 0)  # Monday 03:00 UTC
        session = sf.get_session(dt)
        assert session == SessionName.CLOSED

    def test_weekend_blocked(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 7, 14, 0)  # Saturday
        ok, msg = sf.should_trade(dt)
        assert ok is False
        assert "weekend" in msg.lower()

    def test_weekday_active_session(self):
        sf = SessionFilter()
        dt = datetime(2025, 6, 2, 10, 0)  # Monday London
        ok, msg = sf.should_trade(dt)
        assert ok is True


class TestNewsFilter:

    def test_no_blackout_without_events(self):
        nf = NewsFilter()
        is_blackout, msg = nf.is_blackout("EURUSD")
        assert is_blackout is False

    def test_symbol_currencies(self):
        currencies = NewsFilter._symbol_currencies("EURUSD")
        assert "EUR" in currencies
        assert "USD" in currencies

    def test_crypto_currencies(self):
        currencies = NewsFilter._symbol_currencies("BTCUSDT")
        assert "USD" in currencies
        assert "BTC" in currencies
