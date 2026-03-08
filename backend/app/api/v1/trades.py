from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from typing import List, Optional
from datetime import datetime, timezone

from app.database import get_db
from app.models.trade import Trade, TradeStatus
from app.schemas.trade import TradeRead, TradeUpdate, TradeStats

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("/", response_model=List[TradeRead])
async def list_trades(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    market: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Trade).order_by(desc(Trade.created_at))

    if status:
        stmt = stmt.where(Trade.status == status.upper())
    if symbol:
        stmt = stmt.where(Trade.symbol == symbol.upper())
    if market:
        stmt = stmt.where(Trade.market == market.upper())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/open", response_model=List[TradeRead])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    stmt = select(Trade).where(Trade.status == TradeStatus.OPEN).order_by(desc(Trade.opened_at))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/stats", response_model=TradeStats)
async def get_trade_stats(
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Trade).where(Trade.status == TradeStatus.CLOSED)
    if symbol:
        stmt = stmt.where(Trade.symbol == symbol.upper())

    result = await db.execute(stmt)
    trades = result.scalars().all()

    if not trades:
        return TradeStats(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0.0, total_pnl=0.0, avg_pnl=0.0,
            best_trade=0.0, worst_trade=0.0, avg_confidence=0.0,
        )

    pnls = [t.pnl or 0.0 for t in trades]
    wins = [t for t in trades if (t.pnl or 0) > 0]
    confidences = [t.confidence_score for t in trades if t.confidence_score is not None]

    return TradeStats(
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(trades) - len(wins),
        win_rate=round(len(wins) / len(trades) * 100, 2),
        total_pnl=round(sum(pnls), 2),
        avg_pnl=round(sum(pnls) / len(pnls), 2),
        best_trade=round(max(pnls), 2),
        worst_trade=round(min(pnls), 2),
        avg_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
    )


@router.get("/{trade_id}", response_model=TradeRead)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.patch("/{trade_id}", response_model=TradeRead)
async def update_trade(
    trade_id: int,
    update: TradeUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")

    for field, value in update.model_dump(exclude_none=True).items():
        setattr(trade, field, value)

    if update.status == TradeStatus.CLOSED and trade.closed_at is None:
        trade.closed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(trade)
    return trade
