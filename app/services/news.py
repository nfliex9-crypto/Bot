from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd

from app.core.config import Settings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NewsEvent:
    currency: str
    title: str
    impact: str
    event_time: datetime


class EconomicNewsProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: list[NewsEvent] = []
        self._cached_at: datetime | None = None

    def upcoming_high_impact_events(self) -> list[NewsEvent]:
        if not self.settings.news_filter_enabled:
            return []

        now = datetime.now(timezone.utc)
        if self._cached_at and (now - self._cached_at) < timedelta(minutes=15):
            return self._cache

        try:
            response = httpx.get(self.settings.news_feed_url, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            events = self._parse_events(data)
            self._cache = events
            self._cached_at = now
            return events
        except Exception as exc:
            logger.warning("News feed unavailable: %s", exc)
            if self.settings.news_fail_open:
                return []
            raise

    def _parse_events(self, payload: list[dict] | dict) -> list[NewsEvent]:
        if isinstance(payload, dict):
            rows = payload.get("events", [])
        else:
            rows = payload

        events: list[NewsEvent] = []
        for row in rows:
            impact_value = str(
                row.get("impact")
                or row.get("impactTitle")
                or row.get("importance")
                or row.get("priority")
                or ""
            ).lower()
            if "high" not in impact_value and impact_value not in {"3", "4"}:
                continue

            timestamp_value = (
                row.get("dateUtc")
                or row.get("date")
                or row.get("datetime")
                or row.get("timestamp")
            )
            if not timestamp_value:
                continue
            event_time = pd.to_datetime(timestamp_value, utc=True, errors="coerce")
            if pd.isna(event_time):
                continue

            currency = str(row.get("currency") or row.get("symbol") or row.get("country") or "").upper()
            title = str(row.get("title") or row.get("event") or row.get("name") or "Untitled event")
            events.append(
                NewsEvent(
                    currency=currency,
                    title=title,
                    impact=impact_value,
                    event_time=event_time.to_pydatetime(),
                )
            )
        return events
