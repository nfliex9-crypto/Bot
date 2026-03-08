"""Tests for the trading session filter."""
import pytest
from datetime import datetime, timezone
from src.filters.session_filter import SessionFilter, TradingSession


@pytest.fixture
def session_filter():
    return SessionFilter()


def _utc(hour, minute=0):
    return datetime(2024, 1, 15, hour, minute, 0, tzinfo=timezone.utc)


def test_london_session_allowed(session_filter):
    # 09:00 UTC is London session
    check = session_filter.check(_utc(9, 0))
    assert check.allowed is True
    assert check.session == TradingSession.LONDON


def test_new_york_session_allowed(session_filter):
    # 14:00 UTC is NY session
    check = session_filter.check(_utc(14, 0))
    assert check.allowed is True
    assert check.session in (TradingSession.NEW_YORK, TradingSession.OVERLAP)


def test_overlap_session(session_filter):
    # 13:00 UTC is London/NY overlap
    check = session_filter.check(_utc(13, 0))
    assert check.allowed is True
    assert check.session == TradingSession.OVERLAP


def test_asian_session_blocked(session_filter):
    # 03:00 UTC is Asian session — not in allowed list
    check = session_filter.check(_utc(3, 0))
    assert check.allowed is False


def test_closed_session_blocked(session_filter):
    # 22:00 UTC should be after NY close
    check = session_filter.check(_utc(22, 0))
    assert check.allowed is False


def test_minutes_to_next_session_populated_when_blocked(session_filter):
    check = session_filter.check(_utc(22, 0))
    assert check.minutes_to_next_open is not None
    assert check.minutes_to_next_open > 0


def test_london_open_boundary(session_filter):
    # Exactly at 07:00 should be London
    check = session_filter.check(_utc(7, 0))
    assert check.allowed is True
    assert check.session == TradingSession.LONDON


def test_london_close_boundary(session_filter):
    # At 16:00 London is closed (exclusive end)
    check = session_filter.check(_utc(16, 0))
    # Could be NY only
    assert check.session in (TradingSession.NEW_YORK, TradingSession.CLOSED)
