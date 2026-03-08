from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


class SessionFilter:
    def __init__(self) -> None:
        self.london_tz = ZoneInfo("Europe/London")
        self.new_york_tz = ZoneInfo("America/New_York")

    def is_session_open(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self._in_london(now) or self._in_new_york(now)

    def session_score(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        london = self._in_london(now)
        new_york = self._in_new_york(now)
        if london and new_york:
            return 1.0
        if london or new_york:
            return 0.8
        return 0.0

    def _in_london(self, now: datetime) -> bool:
        london_now = now.astimezone(self.london_tz)
        return time(7, 0) <= london_now.time() <= time(17, 0)

    def _in_new_york(self, now: datetime) -> bool:
        ny_now = now.astimezone(self.new_york_tz)
        return time(8, 0) <= ny_now.time() <= time(17, 0)
