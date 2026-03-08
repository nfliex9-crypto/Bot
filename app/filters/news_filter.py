from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
from loguru import logger

from app.core.config import settings

CURRENCY_MAP = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "EUR": ["EURUSD"],
    "GBP": ["GBPUSD"],
    "JPY": ["USDJPY"],
    "AUD": ["AUDUSD"],
    "CAD": ["USDCAD"],
}


class NewsEvent:
    def __init__(self, title: str, currency: str, impact: str, dt: datetime) -> None:
        self.title = title
        self.currency = currency
        self.impact = impact
        self.datetime = dt

    def affects_symbol(self, symbol: str) -> bool:
        affected = CURRENCY_MAP.get(self.currency, [])
        return symbol in affected


class NewsFilter:
    """
    Fetches high-impact economic news and blocks trading around events.
    Default buffer: 30 minutes before and 15 minutes after.
    """

    def __init__(
        self,
        minutes_before: int = 30,
        minutes_after: int = 15,
    ) -> None:
        self._before = timedelta(minutes=minutes_before)
        self._after = timedelta(minutes=minutes_after)
        self._events: list[NewsEvent] = []
        self._last_fetch: datetime | None = None

    async def refresh(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(settings.forex_factory_url)
                resp.raise_for_status()
                data = resp.json()

            self._events = []
            for item in data:
                impact = item.get("impact", "")
                if impact not in ("High", "Medium"):
                    continue

                date_str = item.get("date", "")
                if not date_str:
                    continue

                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

                self._events.append(
                    NewsEvent(
                        title=item.get("title", ""),
                        currency=item.get("country", ""),
                        impact=impact,
                        dt=dt,
                    )
                )

            self._last_fetch = datetime.now(timezone.utc)
            logger.info(f"News filter refreshed: {len(self._events)} high-impact events")

        except Exception as exc:
            logger.error(f"Failed to fetch news calendar: {exc}")

    def is_safe_to_trade(self, symbol: str) -> tuple[bool, str]:
        """Check if it's safe to open a trade on the given symbol right now."""
        now = datetime.now(timezone.utc)

        for event in self._events:
            if not event.affects_symbol(symbol):
                continue

            window_start = event.datetime - self._before
            window_end = event.datetime + self._after

            if window_start <= now <= window_end:
                reason = (
                    f"High-impact news: {event.title} ({event.currency}) "
                    f"at {event.datetime.strftime('%H:%M UTC')}"
                )
                logger.info(f"News filter blocking {symbol}: {reason}")
                return False, reason

        return True, ""

    @property
    def upcoming_events(self) -> list[NewsEvent]:
        now = datetime.now(timezone.utc)
        return [e for e in self._events if e.datetime > now]
