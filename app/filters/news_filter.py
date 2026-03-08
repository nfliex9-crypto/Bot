"""High-impact news filter - avoid trading around major economic events."""
from datetime import datetime, timezone, timedelta

# Fallback: hardcoded high-impact event window (minutes before/after)
# In production, use Forex Factory, Investing.com, or similar API
NEWS_BUFFER_MINUTES = 30  # No trading 30 min before and after high-impact news


def fetch_high_impact_events(date: datetime | None = None) -> list[dict]:
    """
    Fetch high-impact economic events.
    Placeholder: returns empty list. Integrate with:
    - Forex Factory calendar
    - Investing.com economic calendar
    - MQL5 calendar
    """
    # Placeholder - no external API by default to avoid dependencies
    return []


def is_near_high_impact_news(utc_now: datetime | None = None) -> bool:
    """
    Check if we're within buffer of high-impact news.
    Without external calendar, returns False (allow trading).
    """
    events = fetch_high_impact_events(utc_now or datetime.now(timezone.utc))
    now = utc_now or datetime.now(timezone.utc)
    buffer = timedelta(minutes=NEWS_BUFFER_MINUTES)
    for ev in events:
        ev_time = ev.get("time")
        if ev_time and isinstance(ev_time, datetime):
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            if abs((now - ev_time).total_seconds()) < buffer.total_seconds():
                return True
    return False


def news_filter_passed(utc_now: datetime | None = None) -> tuple[bool, str]:
    """
    Returns (passed, reason).
    Passed=True means no high-impact news in buffer - safe to trade.
    """
    if is_near_high_impact_news(utc_now):
        return False, "High-impact news event in buffer window"
    return True, "No high-impact news in buffer"
