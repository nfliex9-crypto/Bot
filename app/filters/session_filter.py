"""Session filter: London + New York trading hours."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# London: 08:00-17:00 UTC (winter) / 07:00-16:00 UTC (summer - BST)
# New York: 13:00-22:00 UTC (winter) / 12:00-21:00 UTC (summer - EDT)
# Overlap: 13:00-17:00 UTC (best liquidity)

LONDON_OPEN = 8   # UTC
LONDON_CLOSE = 17
NY_OPEN = 13
NY_CLOSE = 22


def is_london_session(utc_now: datetime | None = None) -> bool:
    """Check if current time is within London session."""
    now = utc_now or datetime.now(timezone.utc)
    hour = now.hour
    return LONDON_OPEN <= hour < LONDON_CLOSE


def is_new_york_session(utc_now: datetime | None = None) -> bool:
    """Check if current time is within New York session."""
    now = utc_now or datetime.now(timezone.utc)
    hour = now.hour
    return NY_OPEN <= hour < NY_CLOSE


def is_trading_session(utc_now: datetime | None = None) -> bool:
    """True if London OR New York session (or overlap)."""
    return is_london_session(utc_now) or is_new_york_session(utc_now)


def session_filter_passed(utc_now: datetime | None = None) -> tuple[bool, str]:
    """
    Returns (passed, reason).
    Passed=True means we're in London or NY session and can trade.
    """
    if is_trading_session(utc_now):
        return True, "In London or New York session"
    return False, "Outside London/New York trading hours"
