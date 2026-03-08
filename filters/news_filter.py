from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp

from config.settings import settings
from core.models import NewsEvent

logger = logging.getLogger(__name__)

FOREX_FACTORY_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


class NewsFilter:
    """Filters out trading during high-impact news events."""

    def __init__(self) -> None:
        self._events: List[NewsEvent] = []
        self._last_fetch: Optional[datetime] = None
        self._blackout = timedelta(minutes=settings.news_blackout_minutes)

    async def refresh(self) -> None:
        if not settings.forex_factory_enabled:
            return

        if self._last_fetch and (datetime.utcnow() - self._last_fetch).seconds < 3600:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FOREX_FACTORY_CALENDAR_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("News calendar fetch failed: %d", resp.status)
                        return
                    data = await resp.json(content_type=None)

            self._events = []
            for item in data:
                impact = item.get("impact", "").lower()
                if "high" not in impact:
                    continue
                try:
                    dt_str = item.get("date", "")
                    event_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    self._events.append(NewsEvent(
                        title=item.get("title", ""),
                        currency=item.get("country", ""),
                        impact=impact,
                        datetime_utc=event_dt,
                        forecast=item.get("forecast", ""),
                        previous=item.get("previous", ""),
                    ))
                except Exception:
                    continue

            self._last_fetch = datetime.utcnow()
            logger.info("Loaded %d high-impact news events", len(self._events))

        except Exception:
            logger.exception("Failed to fetch news calendar")

    def is_blackout(self, symbol: str, utc_now: datetime | None = None) -> tuple[bool, str]:
        """Check if we're within the blackout window of a high-impact event."""
        if not settings.forex_factory_enabled:
            return False, ""

        now = utc_now or datetime.utcnow()
        currencies = self._symbol_currencies(symbol)

        for event in self._events:
            if event.currency.upper() not in currencies:
                continue
            delta = abs((event.datetime_utc - now).total_seconds())
            if delta < self._blackout.total_seconds():
                return True, f"News blackout: {event.title} ({event.currency}) at {event.datetime_utc}"

        return False, ""

    @staticmethod
    def _symbol_currencies(symbol: str) -> set[str]:
        clean = symbol.upper().replace("/", "").replace("-", "")
        currencies = set()
        if "USDT" in clean:
            currencies.add("USD")
            currencies.add(clean.replace("USDT", ""))
        elif len(clean) == 6:
            currencies.add(clean[:3])
            currencies.add(clean[3:])
        else:
            currencies.add(clean)
        return currencies

    @property
    def upcoming_events(self) -> List[NewsEvent]:
        now = datetime.utcnow()
        return [e for e in self._events if e.datetime_utc > now]
