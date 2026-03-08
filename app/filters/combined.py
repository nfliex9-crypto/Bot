"""Combined filter: session + news."""
from datetime import datetime, timezone

from .session_filter import session_filter_passed
from .news_filter import news_filter_passed


def all_filters_passed(utc_now: datetime | None = None) -> tuple[bool, list[str]]:
    """
    Run all filters. Returns (passed, list of rejection reasons).
    If passed=True, reasons is empty. If passed=False, reasons list why.
    """
    reasons = []
    now = utc_now or datetime.now(timezone.utc)

    session_ok, session_msg = session_filter_passed(now)
    if not session_ok:
        reasons.append(session_msg)

    news_ok, news_msg = news_filter_passed(now)
    if not news_ok:
        reasons.append(news_msg)

    return len(reasons) == 0, reasons
