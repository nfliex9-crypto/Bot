from __future__ import annotations

import logging
from datetime import datetime

from config.settings import settings
from core.enums import SessionName

logger = logging.getLogger(__name__)


class SessionFilter:
    """Only allows trading during London and New York sessions."""

    def is_active_session(self, utc_now: datetime | None = None) -> bool:
        now = utc_now or datetime.utcnow()
        return self.get_session(now) != SessionName.CLOSED

    def get_session(self, utc_now: datetime | None = None) -> SessionName:
        now = utc_now or datetime.utcnow()
        hour = now.hour

        london = settings.london_open <= hour < settings.london_close
        ny = settings.newyork_open <= hour < settings.newyork_close

        if london and ny:
            return SessionName.OVERLAP
        elif london:
            return SessionName.LONDON
        elif ny:
            return SessionName.NEW_YORK
        return SessionName.CLOSED

    def should_trade(self, utc_now: datetime | None = None) -> tuple[bool, str]:
        now = utc_now or datetime.utcnow()

        if now.weekday() >= 5:
            return False, "Weekend — market closed"

        session = self.get_session(now)
        if session == SessionName.CLOSED:
            return False, f"Outside trading sessions (UTC hour: {now.hour})"

        return True, f"Active session: {session.value}"
