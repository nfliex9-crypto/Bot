"""
High-impact news filter.
Fetches economic calendar data and blocks trading around
high-impact events to avoid volatility spikes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp

from config.settings import NewsConfig
from core.logger import get_logger

logger = get_logger("filters.news")


class NewsEvent:
    def __init__(self, title: str, country: str, impact: str, time: datetime):
        self.title = title
        self.country = country
        self.impact = impact
        self.time = time

    def __repr__(self):
        return f"NewsEvent({self.title}, {self.impact}, {self.time})"


class NewsFilter:
    def __init__(self, config: NewsConfig):
        self.config = config
        self.events: List[NewsEvent] = []
        self._last_fetch: Optional[datetime] = None

    async def fetch_events(self):
        """Fetch this week's economic calendar."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.config.api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"News API returned {resp.status}")
                        return

                    data = await resp.json(content_type=None)
                    self.events = []

                    for item in data:
                        impact = item.get("impact", "").lower()
                        if impact not in ("high", "medium"):
                            continue

                        try:
                            event_time = datetime.strptime(
                                f"{item.get('date', '')} {item.get('time', '00:00')}",
                                "%Y-%m-%dT%H:%M:%S%z %H:%M"
                            )
                        except (ValueError, TypeError):
                            try:
                                date_str = item.get("date", "")
                                time_str = item.get("time", "12:00am")
                                event_time = self._parse_event_time(date_str, time_str)
                            except Exception:
                                continue

                        self.events.append(NewsEvent(
                            title=item.get("title", "Unknown"),
                            country=item.get("country", ""),
                            impact=impact,
                            time=event_time,
                        ))

                    self._last_fetch = datetime.utcnow()
                    logger.info(f"Loaded {len(self.events)} high/medium impact news events")

        except Exception as e:
            logger.warning(f"Failed to fetch news: {e}")

    def _parse_event_time(self, date_str: str, time_str: str) -> datetime:
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%b %d", "%m-%d"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            dt = datetime.utcnow()

        hour, minute = 12, 0
        try:
            time_str = time_str.strip().lower()
            if ":" in time_str:
                parts = time_str.replace("am", "").replace("pm", "").split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                if "pm" in time_str and hour < 12:
                    hour += 12
        except (ValueError, IndexError):
            pass

        return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def is_safe_to_trade(self, symbol: str, now: datetime | None = None) -> tuple[bool, str]:
        """
        Check if it's safe to trade given upcoming news events.
        Returns (is_safe, reason).
        """
        if now is None:
            now = datetime.utcnow()

        before = timedelta(minutes=self.config.minutes_before)
        after = timedelta(minutes=self.config.minutes_after)

        currencies = self._symbol_currencies(symbol)

        for event in self.events:
            if event.impact != "high":
                continue

            if event.country.upper() in currencies or event.country.upper() in ("ALL", "USD"):
                if (event.time - before) <= now <= (event.time + after):
                    return False, f"High-impact news: {event.title} ({event.country}) at {event.time}"

        return True, "OK"

    def _symbol_currencies(self, symbol: str) -> set:
        symbol = symbol.upper()
        currencies = set()
        if len(symbol) == 6:
            currencies.add(symbol[:3])
            currencies.add(symbol[3:])
        elif symbol.endswith("USDT"):
            currencies.add("USD")
            currencies.add(symbol[:-4])
        else:
            currencies.add(symbol)
        return currencies

    async def refresh_if_needed(self):
        """Refresh news data every 4 hours."""
        if self._last_fetch is None or (datetime.utcnow() - self._last_fetch).total_seconds() > 14400:
            await self.fetch_events()
