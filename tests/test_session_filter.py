from datetime import UTC, datetime

from app.config import Settings
from app.filters.session import SessionFilter


def test_session_filter_allows_london_or_newyork():
    settings = Settings()
    filt = SessionFilter(settings)

    allowed_time = datetime(2026, 3, 9, 13, 0, tzinfo=UTC)
    blocked_time = datetime(2026, 3, 9, 1, 0, tzinfo=UTC)

    assert filt.allow(allowed_time) is True
    assert filt.allow(blocked_time) is False

