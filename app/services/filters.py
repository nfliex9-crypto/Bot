from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.domain.models import FilterResult, Market
from app.services.news import EconomicNewsProvider


class TradingFilters:
    def __init__(self, settings: Settings, news_provider: EconomicNewsProvider) -> None:
        self.settings = settings
        self.news_provider = news_provider

    def evaluate(self, market: Market, symbol: str, now: datetime | None = None) -> FilterResult:
        current = now or datetime.now(timezone.utc)
        session_label = self._session_label(current)
        if session_label == "closed":
            return FilterResult(passed=False, session_label=session_label, blocked_reason="outside_session")

        news_block = self._news_block(symbol=symbol, market=market, now=current)
        if news_block:
            return FilterResult(
                passed=False,
                session_label=session_label,
                blocked_reason=f"high_impact_news:{news_block}",
            )

        return FilterResult(passed=True, session_label=session_label)

    def _session_label(self, now: datetime) -> str:
        london_time = now.astimezone(ZoneInfo(self.settings.london_timezone))
        new_york_time = now.astimezone(ZoneInfo(self.settings.new_york_timezone))

        london_open = self.settings.london_open_hour <= london_time.hour < self.settings.london_close_hour
        ny_open = self.settings.new_york_open_hour <= new_york_time.hour < self.settings.new_york_close_hour

        if london_open and ny_open:
            return "london_newyork_overlap"
        if london_open:
            return "london"
        if ny_open:
            return "new_york"
        return "closed"

    def _news_block(self, symbol: str, market: Market, now: datetime) -> str | None:
        if not self.settings.news_filter_enabled:
            return None

        symbols_to_watch = self._symbol_currencies(symbol, market)
        before = timedelta(minutes=self.settings.news_blackout_minutes_before)
        after = timedelta(minutes=self.settings.news_blackout_minutes_after)

        for event in self.news_provider.upcoming_high_impact_events():
            if event.currency and event.currency not in symbols_to_watch:
                continue
            if (event.event_time - before) <= now <= (event.event_time + after):
                return f"{event.currency}:{event.title}"
        return None

    @staticmethod
    def _symbol_currencies(symbol: str, market: Market) -> set[str]:
        if market == Market.FOREX and len(symbol) >= 6:
            return {symbol[:3], symbol[3:6], "USD"}
        if symbol.endswith("USDT"):
            return {"USD", "USDT"}
        return {"USD"}
