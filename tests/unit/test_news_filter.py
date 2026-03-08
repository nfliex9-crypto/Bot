"""Tests for news and session filters."""
import pytest
from datetime import datetime, timezone, timedelta
from src.filters.news_filter import NewsFilter, NewsEvent


@pytest.fixture
def news_filter():
    return NewsFilter()


@pytest.mark.asyncio
async def test_news_filter_clear_no_events(news_filter):
    check = await news_filter.check("EURUSD")
    # With no events loaded, should be clear
    assert check.clear is True


@pytest.mark.asyncio
async def test_news_filter_blocks_on_high_impact(news_filter):
    now = datetime.now(tz=timezone.utc)
    event = NewsEvent(
        title="US Non-Farm Payrolls",
        currency="USD",
        impact="high",
        event_time=now + timedelta(minutes=5),
    )
    news_filter.add_manual_event(event)
    check = await news_filter.check("EURUSD", now=now)
    assert check.clear is False
    assert len(check.blocking_events) >= 1


@pytest.mark.asyncio
async def test_news_filter_ignores_medium_impact(news_filter):
    now = datetime.now(tz=timezone.utc)
    event = NewsEvent(
        title="Some Medium Impact Event",
        currency="USD",
        impact="medium",
        event_time=now + timedelta(minutes=5),
    )
    news_filter.add_manual_event(event)
    check = await news_filter.check("EURUSD", now=now)
    assert check.clear is True


@pytest.mark.asyncio
async def test_news_filter_past_event_no_block(news_filter):
    now = datetime.now(tz=timezone.utc)
    event = NewsEvent(
        title="Past Event",
        currency="USD",
        impact="high",
        event_time=now - timedelta(hours=2),  # Well outside the blackout window
    )
    news_filter.add_manual_event(event)
    check = await news_filter.check("EURUSD", now=now)
    assert check.clear is True


@pytest.mark.asyncio
async def test_news_filter_irrelevant_currency(news_filter):
    now = datetime.now(tz=timezone.utc)
    # JPY news should not block EURUSD
    event = NewsEvent(
        title="BOJ Rate Decision",
        currency="JPY",
        impact="high",
        event_time=now + timedelta(minutes=5),
    )
    news_filter.add_manual_event(event)
    check = await news_filter.check("EURUSD", now=now)
    assert check.clear is True


def test_upcoming_events_returns_list(news_filter):
    now = datetime.now(tz=timezone.utc)
    event = NewsEvent(
        title="Test Event",
        currency="EUR",
        impact="high",
        event_time=now + timedelta(hours=2),
    )
    news_filter.add_manual_event(event)
    upcoming = news_filter.get_upcoming_events(hours_ahead=4)
    assert isinstance(upcoming, list)
