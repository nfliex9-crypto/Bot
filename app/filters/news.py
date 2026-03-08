from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.core.config import Settings
from app.domain.models import EconomicEvent


class HighImpactNewsFilter:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def sync_events(self) -> list[EconomicEvent]:
        if not self.settings.news_sync_url:
            return []
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self.settings.news_sync_url)
            response.raise_for_status()
            payload = response.json()
        return [self._parse_event(item) for item in payload]

    def blocks_trade(
        self,
        events: list[EconomicEvent],
        currencies: list[str],
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(UTC)
        before = timedelta(minutes=self.settings.news_blackout_before_minutes)
        after = timedelta(minutes=self.settings.news_blackout_after_minutes)
        currency_set = {currency.upper() for currency in currencies}
        for event in events:
            if event.impact.lower() != "high":
                continue
            if event.currency.upper() not in currency_set:
                continue
            if event.starts_at - before <= now <= event.starts_at + after:
                return True
        return False

    def news_risk_score(
        self,
        events: list[EconomicEvent],
        currencies: list[str],
        now: datetime | None = None,
    ) -> float:
        return 1.0 if self.blocks_trade(events, currencies, now) else 0.0

    def _parse_event(self, item: dict[str, Any]) -> EconomicEvent:
        starts_at = item.get("starts_at") or item.get("date") or item.get("time")
        if isinstance(starts_at, str):
            starts_at = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        return EconomicEvent(
            title=item.get("title", "event"),
            currency=item.get("currency", "USD"),
            impact=item.get("impact", "high"),
            starts_at=starts_at,
            source=item.get("source", "api"),
        )
