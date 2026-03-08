from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import Settings


class SessionFilter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.london_tz = ZoneInfo("Europe/London")
        self.newyork_tz = ZoneInfo("America/New_York")

    def allow(self, now_utc: datetime) -> bool:
        london = now_utc.astimezone(self.london_tz)
        newyork = now_utc.astimezone(self.newyork_tz)

        london_ok = self.settings.session_london_start <= london.hour < self.settings.session_london_end
        newyork_ok = self.settings.session_newyork_start <= newyork.hour < self.settings.session_newyork_end
        return london_ok or newyork_ok

