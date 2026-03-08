"""
Tests for session filter and news filter.
"""

import pytest
from datetime import datetime
from config.settings import SessionConfig, NewsConfig
from filters.session_filter import SessionFilter
from filters.news_filter import NewsFilter, NewsEvent


@pytest.fixture
def session_filter():
    return SessionFilter(SessionConfig())


class TestSessionFilter:
    def test_london_session_active(self, session_filter):
        london_time = datetime(2025, 3, 10, 10, 0, 0)
        assert session_filter.is_active_session(london_time) is True

    def test_newyork_session_active(self, session_filter):
        ny_time = datetime(2025, 3, 10, 15, 0, 0)
        assert session_filter.is_active_session(ny_time) is True

    def test_overlap_session(self, session_filter):
        overlap = datetime(2025, 3, 10, 14, 0, 0)
        sessions = session_filter.get_active_sessions(overlap)
        assert "london" in sessions
        assert "newyork" in sessions

    def test_outside_session(self, session_filter):
        asia = datetime(2025, 3, 10, 3, 0, 0)
        assert session_filter.is_active_session(asia) is False

    def test_time_until_next(self, session_filter):
        early = datetime(2025, 3, 10, 5, 0, 0)
        wait = session_filter.time_until_next_session(early)
        assert wait > 0


class TestNewsFilter:
    def test_safe_when_no_events(self):
        nf = NewsFilter(NewsConfig())
        safe, reason = nf.is_safe_to_trade("EURUSD")
        assert safe is True

    def test_blocked_during_high_impact(self):
        nf = NewsFilter(NewsConfig(minutes_before=30, minutes_after=30))
        now = datetime(2025, 3, 10, 14, 30, 0)
        nf.events = [
            NewsEvent("NFP", "USD", "high", datetime(2025, 3, 10, 14, 30, 0))
        ]
        safe, reason = nf.is_safe_to_trade("EURUSD", now)
        assert safe is False
        assert "NFP" in reason

    def test_safe_after_event_window(self):
        nf = NewsFilter(NewsConfig(minutes_before=30, minutes_after=30))
        now = datetime(2025, 3, 10, 16, 0, 0)
        nf.events = [
            NewsEvent("NFP", "USD", "high", datetime(2025, 3, 10, 14, 30, 0))
        ]
        safe, reason = nf.is_safe_to_trade("EURUSD", now)
        assert safe is True

    def test_unrelated_currency_safe(self):
        nf = NewsFilter(NewsConfig(minutes_before=30, minutes_after=30))
        now = datetime(2025, 3, 10, 14, 30, 0)
        nf.events = [
            NewsEvent("BOJ Rate", "JPY", "high", datetime(2025, 3, 10, 14, 30, 0))
        ]
        safe, reason = nf.is_safe_to_trade("EURUSD", now)
        assert safe is True
