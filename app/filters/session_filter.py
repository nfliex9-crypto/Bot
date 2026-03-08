from __future__ import annotations

from datetime import datetime, time, timezone

from loguru import logger


class TradingSession:
    def __init__(self, name: str, start: time, end: time) -> None:
        self.name = name
        self.start = start
        self.end = end

    def is_active(self, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now(timezone.utc)
        current = now.time()
        if self.start <= self.end:
            return self.start <= current <= self.end
        # Wraps midnight
        return current >= self.start or current <= self.end


LONDON = TradingSession("London", time(7, 0), time(16, 0))
NEW_YORK = TradingSession("New York", time(12, 0), time(21, 0))
OVERLAP = TradingSession("London-NY Overlap", time(12, 0), time(16, 0))
CRYPTO_24H = TradingSession("Crypto", time(0, 0), time(23, 59))


class SessionFilter:
    """
    Only allow forex trades during London and New York sessions.
    Crypto trades are allowed 24/7 but with reduced sizing outside peak hours.
    """

    def __init__(self) -> None:
        self._forex_sessions = [LONDON, NEW_YORK]
        self._crypto_session = CRYPTO_24H

    def is_forex_session_active(self) -> tuple[bool, str]:
        now = datetime.now(timezone.utc)
        active = []
        for session in self._forex_sessions:
            if session.is_active(now):
                active.append(session.name)

        if active:
            return True, f"Active: {', '.join(active)}"

        return False, "Outside London/NY sessions"

    def is_crypto_session_active(self) -> tuple[bool, str]:
        return True, "Crypto 24/7"

    def is_overlap_session(self) -> bool:
        return OVERLAP.is_active()

    def get_session_info(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "utc_time": now.strftime("%H:%M:%S"),
            "london_active": LONDON.is_active(now),
            "new_york_active": NEW_YORK.is_active(now),
            "overlap": OVERLAP.is_active(now),
        }
