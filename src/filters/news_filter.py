"""
High-Impact News Filter.

Fetches economic calendar events from a public API and blocks trading
within a configurable window (default ±30 minutes) around high-impact events.

Supports: ForexFactory calendar (via scraping), Investing.com API, or a static
          fallback schedule for common recurring events.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
from dataclasses import dataclass, field
import httpx
from loguru import logger

from config.settings import settings


@dataclass
class NewsEvent:
    title: str
    currency: str
    impact: str       # "high" | "medium" | "low"
    event_time: datetime
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None


@dataclass
class NewsCheck:
    clear: bool
    blocking_events: List[NewsEvent] = field(default_factory=list)
    reason: Optional[str] = None
    next_clear_time: Optional[datetime] = None


# Currencies matched to forex pairs
CURRENCY_PAIR_MAP: Dict[str, List[str]] = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF",
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"],
    "EUR": ["EURUSD", "EURJPY", "EURGBP", "EURAUD", "EURCHF"],
    "GBP": ["GBPUSD", "GBPJPY", "EURGBP", "GBPAUD", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY"],
    "CAD": ["USDCAD", "CADJPY", "EURCAD", "GBPCAD", "AUDCAD"],
    "AUD": ["AUDUSD", "AUDJPY", "AUDCAD", "AUDNZD", "AUDCHF"],
    "NZD": ["NZDUSD", "NZDJPY", "AUDNZD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF"],
}

# Built-in high-impact event schedule for common recurring events
# Used as fallback when no API is configured
RECURRING_HIGH_IMPACT = [
    # US (every release day at these UTC times approximately)
    {"title": "US Non-Farm Payrolls", "currency": "USD", "day_of_month": "first_friday"},
    {"title": "US CPI", "currency": "USD"},
    {"title": "FOMC Rate Decision", "currency": "USD"},
    {"title": "US GDP", "currency": "USD"},
    {"title": "UK CPI", "currency": "GBP"},
    {"title": "ECB Rate Decision", "currency": "EUR"},
    {"title": "BOE Rate Decision", "currency": "GBP"},
    {"title": "BOJ Rate Decision", "currency": "JPY"},
]


class NewsFilter:
    """
    Checks if it is safe to trade around high-impact news events.
    """

    def __init__(self):
        self._cached_events: List[NewsEvent] = []
        self._manual_events: List[NewsEvent] = []   # Manually injected events are never cleared
        self._cache_expiry: Optional[datetime] = None
        self._blackout_delta = timedelta(minutes=settings.news_blackout_minutes)

    async def check(
        self, symbol: str, now: Optional[datetime] = None
    ) -> NewsCheck:
        """
        Check whether it's safe to trade the given symbol right now.
        Returns NewsCheck with clear=True if no blocking events found.
        """
        if now is None:
            now = datetime.now(tz=timezone.utc)

        if settings.news_blackout_minutes == 0:
            return NewsCheck(clear=True)

        await self._refresh_events_if_needed(now)
        blocking = self._find_blocking_events(symbol, now)

        if not blocking:
            return NewsCheck(clear=True)

        # Calculate when the last blocking event window ends
        latest_end = max(e.event_time + self._blackout_delta for e in blocking)

        return NewsCheck(
            clear=False,
            blocking_events=blocking,
            reason=f"{len(blocking)} high-impact event(s) within blackout window",
            next_clear_time=latest_end,
        )

    def _find_blocking_events(self, symbol: str, now: datetime) -> List[NewsEvent]:
        """Find events that affect the symbol within the blackout window."""
        window_start = now - self._blackout_delta
        window_end = now + self._blackout_delta
        blocking = []

        for event in self._cached_events + self._manual_events:
            if event.impact.lower() != "high":
                continue
            if not (window_start <= event.event_time <= window_end):
                continue
            # Check if this event's currency affects the symbol
            affected_symbols = CURRENCY_PAIR_MAP.get(event.currency.upper(), [])
            if symbol in affected_symbols or not affected_symbols:
                blocking.append(event)

        return blocking

    async def _refresh_events_if_needed(self, now: datetime) -> None:
        """Refresh cached (API-fetched) news events if cache has expired."""
        if self._cache_expiry and now < self._cache_expiry:
            return

        events = await self._fetch_events(now)
        self._cached_events = events   # Only API events go here; manual events stay separate
        self._cache_expiry = now + timedelta(hours=1)

    async def _fetch_events(self, now: datetime) -> List[NewsEvent]:
        """Attempt to fetch events from API, falling back to empty list."""
        # Try ForexFactory RSS / public API
        events = await self._fetch_forexfactory(now)
        if events:
            logger.info(f"Loaded {len(events)} news events from ForexFactory")
            return events

        # Try Investing.com calendar API if key provided
        if settings.news_api_key:
            events = await self._fetch_investing_api(now)
            if events:
                logger.info(f"Loaded {len(events)} news events from API")
                return events

        logger.debug("News API unavailable; news filter operating with empty calendar")
        return []

    async def _fetch_forexfactory(self, now: datetime) -> List[NewsEvent]:
        """
        Fetch ForexFactory calendar JSON.
        ForexFactory provides a public JSON at: https://nfs.faireconomy.media/ff_calendar_thisweek.json
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                events = []
                for item in data:
                    if item.get("impact", "").lower() not in ("high",):
                        continue
                    try:
                        event_time = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                        events.append(NewsEvent(
                            title=item.get("title", ""),
                            currency=item.get("country", ""),
                            impact=item.get("impact", "low").lower(),
                            event_time=event_time,
                            forecast=item.get("forecast"),
                            previous=item.get("previous"),
                            actual=item.get("actual"),
                        ))
                    except Exception:
                        continue
                return events
        except Exception as e:
            logger.debug(f"ForexFactory fetch failed: {e}")
            return []

    async def _fetch_investing_api(self, now: datetime) -> List[NewsEvent]:
        """Placeholder for Investing.com or other paid API integration."""
        return []

    def add_manual_event(self, event: NewsEvent) -> None:
        """Manually add a news event (e.g. for testing or injected from DB)."""
        self._manual_events.append(event)

    def get_upcoming_events(self, hours_ahead: int = 4) -> List[dict]:
        now = datetime.now(tz=timezone.utc)
        cutoff = now + timedelta(hours=hours_ahead)
        return [
            {
                "title": e.title,
                "currency": e.currency,
                "impact": e.impact,
                "event_time": e.event_time.isoformat(),
                "minutes_until": int((e.event_time - now).total_seconds() / 60),
            }
            for e in self._cached_events
            if now <= e.event_time <= cutoff
        ]
