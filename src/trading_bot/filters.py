from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import Settings
from .domain import MarketType, NewsEvent


class SessionFilter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def active_session(self, now: datetime | None = None) -> str | None:
        now = now or datetime.now(timezone.utc)
        hour = now.hour
        if self.settings.london_session_start_utc <= hour < self.settings.london_session_end_utc:
            return "london"
        if self.settings.new_york_session_start_utc <= hour < self.settings.new_york_session_end_utc:
            return "new_york"
        return None


class HighImpactNewsFilter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def is_blocked(
        self,
        *,
        market: MarketType,
        symbol: str,
        now: datetime,
        events: list[NewsEvent],
    ) -> bool:
        if not events:
            return False

        watchlist = self._relevant_currencies(symbol=symbol, market=market)
        window = timedelta(minutes=self.settings.news_block_window_minutes)
        for event in events:
            if event.impact.lower() != "high":
                continue
            if event.currency not in watchlist:
                continue
            if abs(event.starts_at - now) <= window:
                return True
        return False

    @staticmethod
    def _relevant_currencies(symbol: str, market: MarketType) -> set[str]:
        if market == MarketType.CRYPTO:
            return {"USD", "USDT", "BTC", "ETH"}
        if len(symbol) >= 6:
            return {symbol[:3], symbol[3:6], "USD"}
        return {"USD"}
