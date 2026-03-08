from datetime import datetime, time

import pytz


class SessionFilter:
    def __init__(self) -> None:
        self.tz_london = pytz.timezone("Europe/London")
        self.tz_new_york = pytz.timezone("America/New_York")

    def is_allowed(self, now_utc: datetime) -> bool:
        london_time = now_utc.astimezone(self.tz_london).time()
        ny_time = now_utc.astimezone(self.tz_new_york).time()

        london_open = time(7, 0) <= london_time <= time(16, 0)
        ny_open = time(8, 0) <= ny_time <= time(17, 0)
        return london_open or ny_open
