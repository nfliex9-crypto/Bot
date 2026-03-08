from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import Settings


class NewsFilter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _parse_event_time(self, event: dict[str, Any]) -> datetime | None:
        for key in ("datetime", "date_utc", "time_utc"):
            value = event.get(key)
            if isinstance(value, str):
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return dt.astimezone(timezone.utc)
                except ValueError:
                    continue

        date_str = event.get("date")
        time_str = event.get("time")
        if isinstance(date_str, str) and isinstance(time_str, str):
            for fmt in ("%Y-%m-%d %H:%M", "%Y.%m.%d %H:%M", "%b %d %Y %H:%M"):
                try:
                    return datetime.strptime(f"{date_str} {time_str}", fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return None

    def _is_high_impact(self, event: dict[str, Any]) -> bool:
        impact = str(event.get("impact", "")).lower()
        return any(flag in impact for flag in ["high", "red", "3"])

    def has_blocking_news(self) -> tuple[bool, str]:
        if not self.settings.enable_news_filter:
            return False, "News filter disabled"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(self.settings.news_api_url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return False, f"News API unavailable ({exc}); filter bypassed"

        now = datetime.now(timezone.utc)
        horizon = now + timedelta(minutes=self.settings.news_lookahead_minutes)
        if not isinstance(data, list):
            return False, "Unexpected news response format"

        for event in data:
            if not isinstance(event, dict) or not self._is_high_impact(event):
                continue
            event_time = self._parse_event_time(event)
            if event_time is None:
                continue
            if now <= event_time <= horizon:
                title = event.get("title", "High-impact event")
                return True, f"Blocking news: {title} at {event_time.isoformat()}"
        return False, "No blocking high-impact news"

