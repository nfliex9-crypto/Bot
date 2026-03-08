"""
Trading Session Filter.

Only trade during London (07:00–16:00 UTC) and New York (12:00–21:00 UTC) sessions.
The London/New York overlap (12:00–16:00 UTC) is the highest-liquidity window.
"""

from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional
from enum import Enum


class TradingSession(str, Enum):
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "london_ny_overlap"
    ASIAN = "asian"
    CLOSED = "closed"


@dataclass
class SessionCheck:
    allowed: bool
    session: TradingSession
    reason: Optional[str] = None
    minutes_to_next_open: Optional[int] = None


# Session times in UTC
SESSION_TIMES = {
    TradingSession.ASIAN:   (time(0, 0),  time(9, 0)),
    TradingSession.LONDON:  (time(7, 0),  time(16, 0)),
    TradingSession.NEW_YORK: (time(12, 0), time(21, 0)),
    TradingSession.OVERLAP:  (time(12, 0), time(16, 0)),
}

# Allowed sessions for trading
ALLOWED_SESSIONS = {TradingSession.LONDON, TradingSession.NEW_YORK, TradingSession.OVERLAP}


class SessionFilter:
    """
    Determines whether the current time is within an allowed trading session.
    """

    def check(self, now: Optional[datetime] = None) -> SessionCheck:
        if now is None:
            now = datetime.now(tz=timezone.utc)

        current_time = now.time().replace(tzinfo=None)
        session = self._identify_session(current_time)

        if session in ALLOWED_SESSIONS:
            return SessionCheck(
                allowed=True,
                session=session,
            )

        minutes_to_next = self._minutes_to_next_session(current_time)
        return SessionCheck(
            allowed=False,
            session=session,
            reason=f"Outside trading sessions (currently {session.value})",
            minutes_to_next_open=minutes_to_next,
        )

    def _identify_session(self, t: time) -> TradingSession:
        """Determine which session the given UTC time falls in."""
        london_start, london_end = SESSION_TIMES[TradingSession.LONDON]
        ny_start, ny_end = SESSION_TIMES[TradingSession.NEW_YORK]
        overlap_start, overlap_end = SESSION_TIMES[TradingSession.OVERLAP]

        in_london = london_start <= t < london_end
        in_ny = ny_start <= t < ny_end

        if in_london and in_ny:
            return TradingSession.OVERLAP
        if in_london:
            return TradingSession.LONDON
        if in_ny:
            return TradingSession.NEW_YORK

        asian_start, asian_end = SESSION_TIMES[TradingSession.ASIAN]
        if asian_start <= t < asian_end:
            return TradingSession.ASIAN

        return TradingSession.CLOSED

    def _minutes_to_next_session(self, current: time) -> int:
        """Calculate minutes until next London or New York session opens."""
        london_open = time(7, 0)
        ny_open = time(12, 0)

        def _time_to_minutes(t: time) -> int:
            return t.hour * 60 + t.minute

        current_min = _time_to_minutes(current)
        london_min = _time_to_minutes(london_open)
        ny_min = _time_to_minutes(ny_open)

        candidates = []
        for session_min in [london_min, ny_min]:
            diff = session_min - current_min
            if diff < 0:
                diff += 1440  # next day
            candidates.append(diff)

        return min(candidates)

    def get_session_info(self, now: Optional[datetime] = None) -> dict:
        if now is None:
            now = datetime.now(tz=timezone.utc)
        check = self.check(now)
        return {
            "current_session": check.session.value,
            "trading_allowed": check.allowed,
            "utc_hour": now.hour,
            "utc_minute": now.minute,
            "minutes_to_next_open": check.minutes_to_next_open,
        }
