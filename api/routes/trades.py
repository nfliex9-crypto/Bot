from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends

from database.repository import TradeRepository

router = APIRouter(prefix="/api/trades", tags=["trades"])


def get_repo() -> TradeRepository:
    return TradeRepository()


@router.get("/open")
async def open_trades(repo: TradeRepository = Depends(get_repo)):
    return await repo.get_open_trades()


@router.get("/closed")
async def closed_trades(limit: int = 100, repo: TradeRepository = Depends(get_repo)):
    return await repo.get_closed_trades(limit)


@router.get("/today")
async def today_trades(repo: TradeRepository = Depends(get_repo)):
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return await repo.get_trades_since(since)


@router.get("/recent")
async def recent_trades(hours: int = 24, repo: TradeRepository = Depends(get_repo)):
    since = datetime.utcnow() - timedelta(hours=hours)
    return await repo.get_trades_since(since)
