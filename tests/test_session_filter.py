from datetime import datetime, time, timezone

import pytest

from app.filters.session_filter import LONDON, NEW_YORK, SessionFilter, TradingSession


def test_london_session_during_hours():
    dt = datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc)
    assert LONDON.is_active(dt)


def test_london_session_outside_hours():
    dt = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)
    assert not LONDON.is_active(dt)


def test_new_york_session():
    dt = datetime(2024, 1, 15, 15, 0, tzinfo=timezone.utc)
    assert NEW_YORK.is_active(dt)


def test_session_filter_forex():
    sf = SessionFilter()
    active, reason = sf.is_forex_session_active()
    assert isinstance(active, bool)
    assert isinstance(reason, str)


def test_crypto_always_active():
    sf = SessionFilter()
    active, _ = sf.is_crypto_session_active()
    assert active
