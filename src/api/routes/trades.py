from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from src.models.database import Trade, Signal, TradeStatus, get_db
from src.api.schemas import TradeResponse, SignalResponse, ManualTradeRequest

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("/", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all trades with optional filters."""
    query = select(Trade).order_by(desc(Trade.created_at)).limit(limit).offset(offset)
    if status:
        query = query.where(Trade.status == status)
    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
    if market:
        query = query.where(Trade.market == market)

    result = await db.execute(query)
    trades = result.scalars().all()
    return trades


@router.get("/open", response_model=List[TradeResponse])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    """Get all currently open trades."""
    result = await db.execute(
        select(Trade).where(
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE])
        ).order_by(desc(Trade.open_time))
    )
    return result.scalars().all()


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single trade by ID."""
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/history/summary")
async def get_trade_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get performance summary for the past N days."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Trade).where(
            Trade.status == TradeStatus.CLOSED,
            Trade.close_time >= since,
        )
    )
    trades = result.scalars().all()

    if not trades:
        return {"message": "No closed trades in period", "days": days}

    total = len(trades)
    winners = [t for t in trades if float(t.realized_pnl) > 0]
    losers = [t for t in trades if float(t.realized_pnl) <= 0]
    total_pnl = sum(float(t.realized_pnl) for t in trades)
    gross_profit = sum(float(t.realized_pnl) for t in winners)
    gross_loss = abs(sum(float(t.realized_pnl) for t in losers))
    pf = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf")

    return {
        "period_days": days,
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": round(len(winners) / total, 4) if total > 0 else 0,
        "total_pnl": round(total_pnl, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": pf,
        "avg_winner": round(gross_profit / len(winners), 2) if winners else 0,
        "avg_loser": round(gross_loss / len(losers), 2) if losers else 0,
        "best_trade": round(max(float(t.realized_pnl) for t in trades), 2),
        "worst_trade": round(min(float(t.realized_pnl) for t in trades), 2),
    }


@router.get("/signals/recent", response_model=List[SignalResponse])
async def get_recent_signals(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent trade signals."""
    result = await db.execute(
        select(Signal).order_by(desc(Signal.generated_at)).limit(limit)
    )
    return result.scalars().all()
