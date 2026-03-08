from __future__ import annotations

from datetime import datetime, time, timezone
from typing import List, Tuple

from core.models import Session
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_time(time_str: str) -> time:
    h, m = map(int, time_str.split(":"))
    return time(h, m)


def _is_in_window(
    current_utc: time,
    open_str: str,
    close_str: str,
) -> bool:
    open_t = _parse_time(open_str)
    close_t = _parse_time(close_str)
    if open_t < close_t:
        return open_t <= current_utc < close_t
    # Overnight window
    return current_utc >= open_t or current_utc < close_t


class SessionFilter:
    """
    Determines the active trading session and whether a symbol
    should be traded at the current UTC time.

    Active sessions: London (07:00–16:00 UTC) and New York (13:00–22:00 UTC).
    The London/NY overlap (13:00–16:00 UTC) is the highest-liquidity window.
    """

    def __init__(self) -> None:
        from config.settings import settings

        self._london_open = settings.london_open_utc
        self._london_close = settings.london_close_utc
        self._ny_open = settings.new_york_open_utc
        self._ny_close = settings.new_york_close_utc

    # ------------------------------------------------------------------
    def current_session(self, now: datetime | None = None) -> Session:
        if now is None:
            now = datetime.now(timezone.utc)
        t = now.time()

        in_london = _is_in_window(t, self._london_open, self._london_close)
        in_ny = _is_in_window(t, self._ny_open, self._ny_close)

        if in_london and in_ny:
            return Session.LONDON_NY_OVERLAP
        if in_london:
            return Session.LONDON
        if in_ny:
            return Session.NEW_YORK
        return Session.ASIAN

    def is_tradeable(
        self,
        symbol: str,
        now: datetime | None = None,
        allowed_sessions: List[Session] | None = None,
    ) -> bool:
        if allowed_sessions is None:
            allowed_sessions = [
                Session.LONDON,
                Session.NEW_YORK,
                Session.LONDON_NY_OVERLAP,
            ]
        session = self.current_session(now)
        tradeable = session in allowed_sessions
        if not tradeable:
            logger.debug(
                "Session filter: %s is NOT tradeable during %s session",
                symbol,
                session.value,
            )
        return tradeable

    def minutes_to_session_open(self, now: datetime | None = None) -> int:
        """Returns minutes until the next London or NY session opens."""
        if now is None:
            now = datetime.now(timezone.utc)
        if self.is_tradeable(symbol="any", now=now):
            return 0
        london_open = _parse_time(self._london_open)
        ny_open = _parse_time(self._ny_open)
        current_minutes = now.hour * 60 + now.minute
        london_open_minutes = london_open.hour * 60 + london_open.minute
        ny_open_minutes = ny_open.hour * 60 + ny_open.minute

        delta_london = (london_open_minutes - current_minutes) % (24 * 60)
        delta_ny = (ny_open_minutes - current_minutes) % (24 * 60)
        return min(delta_london, delta_ny)


# Module-level singleton
session_filter = SessionFilter()
