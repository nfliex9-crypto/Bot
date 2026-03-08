from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import NewsEvent


def symbol_currencies(symbol: str) -> set[str]:
    if symbol.endswith("USDT"):
        return {"USD"}
    if len(symbol) == 6:
        return {symbol[:3], symbol[3:]}
    return {"USD"}


class HighImpactNewsFilter:
    def __init__(self, block_window_minutes: int = 60) -> None:
        self.block_window = timedelta(minutes=block_window_minutes)

    async def is_allowed(self, session: AsyncSession, symbol: str, now_utc: datetime) -> bool:
        currencies = symbol_currencies(symbol)
        start = now_utc - self.block_window
        end = now_utc + self.block_window
        stmt = (
            select(NewsEvent)
            .where(NewsEvent.impact == "high")
            .where(NewsEvent.currency.in_(currencies))
            .where(NewsEvent.starts_at >= start)
            .where(NewsEvent.starts_at <= end)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return len(rows) == 0
