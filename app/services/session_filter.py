from datetime import datetime, timezone

from app.config import Settings


class SessionFilter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        hour = now.hour
        london_open = self.settings.london_start_hour <= hour < self.settings.london_end_hour
        newyork_open = self.settings.newyork_start_hour <= hour < self.settings.newyork_end_hour
        return london_open or newyork_open

