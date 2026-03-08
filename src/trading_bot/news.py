from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings
from .domain import NewsEvent
from .models import NewsEventRecord


class NewsProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upcoming_events(self, session: Session, now: datetime | None = None) -> list[NewsEvent]:
        now = now or datetime.now(timezone.utc)
        api_events = self._fetch_api_events(now)
        if api_events:
            return api_events

        query = (
            select(NewsEventRecord)
            .where(NewsEventRecord.starts_at >= now - timedelta(hours=1))
            .where(NewsEventRecord.starts_at <= now + timedelta(hours=8))
            .order_by(NewsEventRecord.starts_at.asc())
        )
        records = session.scalars(query).all()
        return [
            NewsEvent(
                title=record.title,
                currency=record.currency,
                impact=record.impact,
                starts_at=record.starts_at.replace(tzinfo=timezone.utc)
                if record.starts_at.tzinfo is None
                else record.starts_at,
                source=record.source,
            )
            for record in records
        ]

    def _fetch_api_events(self, now: datetime) -> list[NewsEvent]:
        if not self.settings.high_impact_news_url:
            return []

        headers = {}
        if self.settings.high_impact_news_api_key:
            headers["Authorization"] = f"Bearer {self.settings.high_impact_news_api_key}"

        try:
            response = httpx.get(self.settings.high_impact_news_url, headers=headers, timeout=5.0)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        events: list[NewsEvent] = []
        for item in payload:
            try:
                event_time = datetime.fromisoformat(item["starts_at"].replace("Z", "+00:00"))
            except Exception:
                continue
            if event_time < now - timedelta(hours=1):
                continue
            events.append(
                NewsEvent(
                    title=item["title"],
                    currency=item["currency"],
                    impact=item.get("impact", "high"),
                    starts_at=event_time.astimezone(timezone.utc),
                    source=item.get("source", "api"),
                )
            )
        return events
