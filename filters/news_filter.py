from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import aiohttp

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


# Currency codes for each Forex pair
_PAIR_CURRENCIES: Dict[str, List[str]] = {
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "AUDUSD": ["AUD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "USDCHF": ["USD", "CHF"],
    "NZDUSD": ["NZD", "USD"],
    "GBPJPY": ["GBP", "JPY"],
    "EURJPY": ["EUR", "JPY"],
}

# High-impact crypto-correlated events
_CRYPTO_HIGH_IMPACT_KEYWORDS = [
    "fed", "fomc", "interest rate", "cpi", "inflation", "nfp", "gdp"
]


class NewsEvent:
    __slots__ = ("event_time", "currency", "impact", "title")

    def __init__(
        self,
        event_time: datetime,
        currency: str,
        impact: str,
        title: str,
    ) -> None:
        self.event_time = event_time
        self.currency = currency.upper()
        self.impact = impact.lower()
        self.title = title

    @property
    def is_high_impact(self) -> bool:
        return self.impact in ("high", "red")


class NewsFilter:
    """
    Downloads the ForexFactory weekly calendar and blocks trading
    around high-impact news events.
    """

    def __init__(self) -> None:
        self._events: List[NewsEvent] = []
        self._last_fetch: Optional[datetime] = None
        self._fetch_interval = timedelta(hours=6)
        self._buffer = timedelta(minutes=settings.news_buffer_minutes)

    # ------------------------------------------------------------------
    async def refresh(self) -> None:
        now = datetime.now(timezone.utc)
        if self._last_fetch and (now - self._last_fetch) < self._fetch_interval:
            return
        try:
            await self._fetch_events()
            self._last_fetch = now
        except Exception as exc:
            logger.warning("News filter: could not refresh events: %s", exc)

    async def _fetch_events(self) -> None:
        url = settings.news_api_url
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        ) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)

        events: List[NewsEvent] = []
        for item in data:
            try:
                dt_str = item.get("date", "") + " " + item.get("time", "")
                # ForexFactory uses "MM-DD-YYYY HH:MM am/pm" format
                event_time = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                event_time = event_time.replace(tzinfo=timezone.utc)
                events.append(
                    NewsEvent(
                        event_time=event_time,
                        currency=item.get("country", ""),
                        impact=item.get("impact", ""),
                        title=item.get("title", ""),
                    )
                )
            except Exception:
                continue

        self._events = events
        logger.info("News filter: loaded %d events", len(events))

    # ------------------------------------------------------------------
    def is_news_window(
        self,
        symbol: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Returns True if there is a high-impact news event within the
        buffer window for the currencies involved in the symbol.
        """
        if not self._events:
            return False

        if now is None:
            now = datetime.now(timezone.utc)

        currencies = self._get_currencies_for_symbol(symbol)
        window_start = now - self._buffer
        window_end = now + self._buffer

        for event in self._events:
            if not event.is_high_impact:
                continue
            if event.currency not in currencies:
                continue
            if window_start <= event.event_time <= window_end:
                logger.info(
                    "News filter: blocking %s — '%s' (%s) at %s",
                    symbol,
                    event.title,
                    event.currency,
                    event.event_time.strftime("%H:%M UTC"),
                )
                return True
        return False

    def next_high_impact_event(
        self, symbol: str, now: Optional[datetime] = None
    ) -> Optional[NewsEvent]:
        if now is None:
            now = datetime.now(timezone.utc)
        currencies = self._get_currencies_for_symbol(symbol)
        upcoming = [
            e
            for e in self._events
            if e.is_high_impact
            and e.currency in currencies
            and e.event_time >= now
        ]
        if not upcoming:
            return None
        return min(upcoming, key=lambda e: e.event_time)

    @staticmethod
    def _get_currencies_for_symbol(symbol: str) -> List[str]:
        symbol_upper = symbol.upper()
        # Crypto: match USD, BTC, ETH etc.
        if symbol_upper.endswith("USDT") or symbol_upper.endswith("BUSD"):
            return ["USD"]
        return _PAIR_CURRENCIES.get(symbol_upper, [symbol_upper[:3], symbol_upper[3:]])

    def get_todays_events(
        self, now: Optional[datetime] = None
    ) -> List[Dict]:
        if now is None:
            now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return [
            {
                "time": e.event_time.strftime("%H:%M UTC"),
                "currency": e.currency,
                "impact": e.impact,
                "title": e.title,
            }
            for e in self._events
            if today_start <= e.event_time < today_end
        ]


# Module-level singleton
news_filter = NewsFilter()
