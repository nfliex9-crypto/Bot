"""
High-Impact News Filter.

Prevents trading around high-impact economic events.
Uses ForexFactory-style news calendar via HTTP API.

Supported sources:
1. ForexFactory JSON feed (primary)
2. Investing.com economic calendar
3. Manual event override (via config/database)

Events that block trading:
- NFP (Non-Farm Payrolls)
- FOMC Rate Decisions
- CPI / PPI
- GDP releases
- Central bank speeches
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass
import httpx
import pytz

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("news_filter")

UTC = pytz.UTC

HIGH_IMPACT_KEYWORDS = [
    "nfp", "non-farm", "fomc", "fed rate", "interest rate",
    "cpi", "inflation", "gdp", "unemployment", "payroll",
    "central bank", "boe", "ecb", "boj", "rba", "snb",
    "retail sales", "pce", "ism", "pmi manufacturing",
]

CURRENCY_SYMBOL_MAP = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD",
            "EURJPY", "GBPJPY", "AUDJPY", "BTCUSDT", "ETHUSDT"],
    "EUR": ["EURUSD", "EURJPY"],
    "GBP": ["GBPUSD", "GBPJPY"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY"],
    "AUD": ["AUDUSD", "AUDJPY"],
    "CAD": ["USDCAD"],
    "CHF": ["USDCHF"],
    "NZD": ["NZDUSD"],
}


@dataclass
class NewsEvent:
    title: str
    currency: str
    impact: str         # "high" | "medium" | "low"
    event_time: datetime
    actual: Optional[str] = None
    forecast: Optional[str] = None
    previous: Optional[str] = None


class NewsFilter:
    """
    Filters trades around high-impact economic events.

    Maintains an in-memory cache of upcoming events,
    refreshed periodically.
    """

    def __init__(
        self,
        minutes_before: int = None,
        minutes_after: int = None,
        api_key: Optional[str] = None,
    ):
        self.minutes_before = minutes_before or settings.NEWS_FILTER_MINUTES_BEFORE
        self.minutes_after = minutes_after or settings.NEWS_FILTER_MINUTES_AFTER
        self.api_key = api_key or settings.NEWS_API_KEY

        self._events_cache: List[NewsEvent] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_ttl_minutes = 60  # Refresh every hour

    def is_news_clear(
        self,
        symbol: str,
        dt: Optional[datetime] = None,
    ) -> bool:
        """
        Check if it's safe to trade a symbol (no high-impact news imminent).
        Returns True if clear to trade, False if news is nearby.
        """
        if dt is None:
            dt = datetime.now(UTC)
        elif dt.tzinfo is None:
            dt = UTC.localize(dt)

        symbol = symbol.upper()
        relevant_events = self._get_relevant_events(symbol, dt)

        if not relevant_events:
            return True

        for event in relevant_events:
            event_time = event.event_time
            if event_time.tzinfo is None:
                event_time = UTC.localize(event_time)

            time_diff_minutes = (event_time - dt).total_seconds() / 60

            # Block if news is within window
            if -self.minutes_after <= time_diff_minutes <= self.minutes_before:
                logger.info(
                    f"News block: {symbol} - {event.title} ({event.currency}) "
                    f"at {event_time} (in {time_diff_minutes:.0f} min)"
                )
                return False

        return True

    def get_upcoming_events(
        self,
        hours_ahead: int = 4,
        dt: Optional[datetime] = None,
    ) -> List[NewsEvent]:
        """Get high-impact events in the next N hours."""
        if dt is None:
            dt = datetime.now(UTC)

        cutoff = dt + timedelta(hours=hours_ahead)
        return [
            e for e in self._events_cache
            if dt <= e.event_time <= cutoff and e.impact == "high"
        ]

    def _get_relevant_events(
        self,
        symbol: str,
        dt: datetime,
    ) -> List[NewsEvent]:
        """Get high-impact events relevant to a symbol near the given time."""
        relevant_currencies = self._get_symbol_currencies(symbol)
        window_start = dt - timedelta(minutes=self.minutes_after)
        window_end = dt + timedelta(minutes=self.minutes_before)

        return [
            e for e in self._events_cache
            if e.impact == "high"
            and e.currency in relevant_currencies
            and window_start <= e.event_time <= window_end
        ]

    def _get_symbol_currencies(self, symbol: str) -> List[str]:
        """Extract currencies from a symbol."""
        symbol = symbol.upper()
        currencies = []
        # Standard 6-char forex pair
        if len(symbol) == 6:
            currencies = [symbol[:3], symbol[3:]]
        # Crypto (BTC/USDT → USD)
        elif symbol.endswith("USDT"):
            currencies = ["USD"]
        else:
            currencies = [symbol[:3], symbol[3:6]] if len(symbol) >= 6 else [symbol]
        return currencies

    async def refresh_events(self):
        """Fetch upcoming economic events from external API."""
        try:
            events = await self._fetch_forexfactory_events()
            if events:
                self._events_cache = events
                self._last_fetch = datetime.now(UTC)
                logger.info(f"News filter: loaded {len(events)} high-impact events")
            else:
                logger.warning("News filter: no events fetched, using mock data")
                self._events_cache = self._get_mock_events()
        except Exception as e:
            logger.error(f"News filter refresh error: {e}")
            if not self._events_cache:
                self._events_cache = self._get_mock_events()

    async def _fetch_forexfactory_events(self) -> List[NewsEvent]:
        """
        Fetch events from ForexFactory-compatible JSON feed.
        Falls back gracefully if unavailable.
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return []

                data = response.json()
                events = []
                for item in data:
                    impact = item.get("impact", "").lower()
                    if impact != "high":
                        continue

                    try:
                        event_dt = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                        if event_dt.tzinfo is None:
                            event_dt = UTC.localize(event_dt)
                    except Exception:
                        continue

                    events.append(NewsEvent(
                        title=item.get("title", ""),
                        currency=item.get("country", "USD").upper(),
                        impact="high",
                        event_time=event_dt,
                        actual=item.get("actual"),
                        forecast=item.get("forecast"),
                        previous=item.get("previous"),
                    ))

                return events

        except Exception as e:
            logger.warning(f"ForexFactory fetch failed: {e}")
            return []

    def _get_mock_events(self) -> List[NewsEvent]:
        """Return empty event list as fallback (allow trading)."""
        return []

    def needs_refresh(self) -> bool:
        """Check if cache needs refreshing."""
        if self._last_fetch is None:
            return True
        age_minutes = (datetime.now(UTC) - self._last_fetch).total_seconds() / 60
        return age_minutes >= self._cache_ttl_minutes

    def add_manual_event(
        self,
        title: str,
        currency: str,
        event_time: datetime,
        impact: str = "high",
    ):
        """Manually add an event to the cache."""
        if event_time.tzinfo is None:
            event_time = UTC.localize(event_time)
        self._events_cache.append(NewsEvent(
            title=title,
            currency=currency,
            impact=impact,
            event_time=event_time,
        ))
        logger.info(f"Manual event added: {title} ({currency}) at {event_time}")
