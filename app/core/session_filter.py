"""
Session Filter.

Only allows trading during London and New York sessions (highest liquidity).
Supports overlap detection (London-NY overlap: 13:00-16:00 UTC).

Sessions (UTC):
- Tokyo:    00:00 - 09:00
- London:   08:00 - 16:00
- New York: 13:00 - 21:00
- Overlap:  13:00 - 16:00 (London + NY both open)
"""
from datetime import datetime, time
from typing import Optional
import pytz
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("session_filter")

UTC = pytz.UTC


class SessionInfo:
    def __init__(
        self,
        name: str,
        is_active: bool,
        session_type: str,
        hours_until_open: Optional[float] = None,
        hours_until_close: Optional[float] = None,
    ):
        self.name = name
        self.is_active = is_active
        self.session_type = session_type    # london | new_york | overlap | off
        self.hours_until_open = hours_until_open
        self.hours_until_close = hours_until_close

    def __repr__(self):
        return f"<Session {self.name} active={self.is_active}>"


class SessionFilter:
    """
    Filters trades based on active trading sessions.

    Allows trading only during London and New York sessions
    (including their overlap), which provide maximum liquidity.
    """

    def __init__(
        self,
        london_open: int = None,
        london_close: int = None,
        ny_open: int = None,
        ny_close: int = None,
        allow_overlap_only: bool = False,
    ):
        self.london_open = london_open or settings.LONDON_OPEN_UTC
        self.london_close = london_close or settings.LONDON_CLOSE_UTC
        self.ny_open = ny_open or settings.NEW_YORK_OPEN_UTC
        self.ny_close = ny_close or settings.NEW_YORK_CLOSE_UTC
        self.allow_overlap_only = allow_overlap_only

    def is_tradeable(self, dt: Optional[datetime] = None) -> bool:
        """
        Return True if current time is within an allowed trading session.
        """
        session = self.get_current_session(dt)
        return session.is_active

    def get_current_session(self, dt: Optional[datetime] = None) -> SessionInfo:
        """
        Get current session information.
        """
        if dt is None:
            dt = datetime.now(UTC)
        elif dt.tzinfo is None:
            dt = UTC.localize(dt)
        else:
            dt = dt.astimezone(UTC)

        hour = dt.hour
        minute = dt.minute
        current_minutes = hour * 60 + minute

        london_open_m = self.london_open * 60
        london_close_m = self.london_close * 60
        ny_open_m = self.ny_open * 60
        ny_close_m = self.ny_close * 60

        in_london = london_open_m <= current_minutes < london_close_m
        in_ny = ny_open_m <= current_minutes < ny_close_m
        overlap_open_m = max(london_open_m, ny_open_m)
        overlap_close_m = min(london_close_m, ny_close_m)
        in_overlap = overlap_open_m <= current_minutes < overlap_close_m

        if in_overlap:
            hours_until_close = (overlap_close_m - current_minutes) / 60
            return SessionInfo(
                name="London-NY Overlap",
                is_active=not self.allow_overlap_only or True,
                session_type="overlap",
                hours_until_close=round(hours_until_close, 2),
            )
        elif in_london:
            hours_until_close = (london_close_m - current_minutes) / 60
            active = not self.allow_overlap_only
            return SessionInfo(
                name="London",
                is_active=active,
                session_type="london",
                hours_until_close=round(hours_until_close, 2),
            )
        elif in_ny:
            hours_until_close = (ny_close_m - current_minutes) / 60
            active = not self.allow_overlap_only
            return SessionInfo(
                name="New York",
                is_active=active,
                session_type="new_york",
                hours_until_close=round(hours_until_close, 2),
            )
        else:
            # Calculate hours until next session
            all_opens = [london_open_m, ny_open_m]
            next_open = None
            min_wait = float("inf")
            for open_m in all_opens:
                wait = (open_m - current_minutes) % (24 * 60)
                if wait < min_wait:
                    min_wait = wait
                    next_open = open_m

            return SessionInfo(
                name="Off Session",
                is_active=False,
                session_type="off",
                hours_until_open=round(min_wait / 60, 2),
            )

    def get_session_name(self, dt: Optional[datetime] = None) -> str:
        """Get session name string for logging."""
        session = self.get_current_session(dt)
        return session.session_type

    def get_next_session_open(self, dt: Optional[datetime] = None) -> Optional[datetime]:
        """Get datetime of next session opening."""
        if dt is None:
            dt = datetime.now(UTC)

        session = self.get_current_session(dt)
        if session.is_active:
            return dt  # Already in session

        # Find next opening
        hour = dt.hour
        current_minutes = hour * 60 + dt.minute

        candidates = [self.london_open * 60, self.ny_open * 60]
        next_minutes = None
        min_wait = float("inf")
        for c in candidates:
            wait = (c - current_minutes) % (24 * 60)
            if wait < min_wait:
                min_wait = wait
                next_minutes = c

        if next_minutes is None:
            return None

        next_dt = dt.replace(
            hour=next_minutes // 60,
            minute=next_minutes % 60,
            second=0,
            microsecond=0,
        )
        if next_dt < dt:
            from datetime import timedelta
            next_dt += timedelta(days=1)
        return next_dt
