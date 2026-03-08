"""
Session filter: only trade during London and New York sessions.
"""

from __future__ import annotations

from datetime import datetime

from config.settings import SessionConfig
from core.logger import get_logger

logger = get_logger("filters.session")


class SessionFilter:
    def __init__(self, config: SessionConfig):
        self.config = config

    def is_active_session(self, now: datetime | None = None) -> bool:
        """Check if current time falls within London or New York session."""
        if now is None:
            now = datetime.utcnow()
        hour = now.hour
        return self._in_london(hour) or self._in_newyork(hour)

    def get_active_sessions(self, now: datetime | None = None) -> list[str]:
        if now is None:
            now = datetime.utcnow()
        hour = now.hour
        sessions = []
        if self._in_london(hour):
            sessions.append("london")
        if self._in_newyork(hour):
            sessions.append("newyork")
        return sessions

    def _in_london(self, hour: int) -> bool:
        return self.config.london_open <= hour < self.config.london_close

    def _in_newyork(self, hour: int) -> bool:
        return self.config.newyork_open <= hour < self.config.newyork_close

    def time_until_next_session(self, now: datetime | None = None) -> int:
        """Minutes until the next session opens."""
        if now is None:
            now = datetime.utcnow()
        hour = now.hour

        if self.is_active_session(now):
            return 0

        next_opens = [self.config.london_open, self.config.newyork_open]
        min_wait = 24 * 60
        for open_hour in next_opens:
            diff = (open_hour - hour) % 24
            wait_minutes = diff * 60 - now.minute
            if wait_minutes < min_wait:
                min_wait = wait_minutes

        return max(0, min_wait)
