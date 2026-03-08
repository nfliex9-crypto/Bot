from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.database import get_db
from app.models.signal import Signal, SignalStatus
from app.schemas.signal import SignalRead, SignalCreate

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("/", response_model=List[SignalRead])
async def list_signals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    market: Optional[str] = None,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Signal).order_by(desc(Signal.created_at))

    if status:
        stmt = stmt.where(Signal.status == status.upper())
    if symbol:
        stmt = stmt.where(Signal.symbol == symbol.upper())
    if market:
        stmt = stmt.where(Signal.market == market.upper())
    if min_confidence is not None:
        stmt = stmt.where(Signal.confidence_score >= min_confidence)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/active", response_model=List[SignalRead])
async def get_active_signals(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Signal)
        .where(Signal.status == SignalStatus.ACTIVE)
        .order_by(desc(Signal.confidence_score))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalRead)
async def get_signal(signal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
