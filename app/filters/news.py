import logging
from datetime import UTC, datetime, timedelta
from typing import Iterable, List

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class NewsFilter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _parse_event_time(self, raw: str) -> datetime | None:
        candidates = ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")
        for fmt in candidates:
            try:
                parsed = datetime.strptime(raw, fmt)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except ValueError:
                continue
        return None

    def _is_high_impact(self, impact: str) -> bool:
        impact_lower = impact.lower().strip()
        if impact_lower in {"high", "3", "red"}:
            return True
        return not self.settings.high_impact_only

    def _extract_events(self, payload: list, related_currencies: Iterable[str]) -> List[datetime]:
        blocked_times: List[datetime] = []
        currency_set = {c.upper() for c in related_currencies}
        for event in payload:
            currency = str(event.get("currency", "")).upper()
            impact = str(event.get("impact", ""))
            raw_time = event.get("date") or event.get("dateUtc") or event.get("timestamp")
            if currency not in currency_set or not raw_time:
                continue
            if not self._is_high_impact(impact):
                continue
            event_time = self._parse_event_time(str(raw_time))
            if event_time:
                blocked_times.append(event_time)
        return blocked_times

    def should_block(self, related_currencies: Iterable[str], now_utc: datetime) -> bool:
        if not self.settings.news_filter_enabled:
            return False

        try:
            response = httpx.get(self.settings.news_api_url, timeout=7.5)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                return False
            blocked_times = self._extract_events(payload, related_currencies)
            cooldown = timedelta(minutes=self.settings.news_cooldown_minutes)
            return any(abs(now_utc - event_time) <= cooldown for event_time in blocked_times)
        except Exception as exc:
            logger.warning("News filter fetch failed; continuing without block: %s", exc)
            return False

