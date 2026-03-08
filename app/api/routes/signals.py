"""
Signal API Routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.signal import Signal, SignalStatus
from app.schemas.signal import SignalResponse

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("/", response_model=List[SignalResponse])
async def list_signals(
    status: Optional[SignalStatus] = None,
    symbol: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List signals with filters."""
    query = select(Signal).order_by(desc(Signal.created_at))
    if status:
        query = query.where(Signal.status == status)
    if symbol:
        query = query.where(Signal.symbol == symbol.upper())
    if direction:
        query = query.where(Signal.direction == direction)
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/latest", response_model=List[SignalResponse])
async def get_latest_signals(
    hours: int = Query(4, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Get signals from the last N hours."""
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Signal)
        .where(Signal.created_at >= since)
        .order_by(desc(Signal.created_at))
        .limit(100)
    )
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific signal."""
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.get("/stats/by-symbol")
async def signal_stats_by_symbol(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get signal statistics grouped by symbol."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Signal).where(Signal.created_at >= since)
    )
    signals = result.scalars().all()

    stats = {}
    for s in signals:
        sym = s.symbol
        if sym not in stats:
            stats[sym] = {
                "total": 0, "executed": 0, "rejected": 0,
                "avg_confidence": 0.0, "confidences": [],
            }
        stats[sym]["total"] += 1
        if s.status == SignalStatus.EXECUTED:
            stats[sym]["executed"] += 1
        elif s.status == SignalStatus.REJECTED:
            stats[sym]["rejected"] += 1
        if s.ai_confidence:
            stats[sym]["confidences"].append(s.ai_confidence)

    for sym in stats:
        confs = stats[sym].pop("confidences", [])
        stats[sym]["avg_confidence"] = round(sum(confs) / len(confs), 4) if confs else 0.0
        total = stats[sym]["total"]
        stats[sym]["execution_rate"] = round(
            stats[sym]["executed"] / total, 4
        ) if total > 0 else 0.0

    return {"period_days": days, "symbols": stats}
