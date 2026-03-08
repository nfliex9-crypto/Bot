"""
Trade Management API Routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.database import get_db
from app.models.trade import Trade, TradeStatus, TradeDirection
from app.schemas.trade import TradeResponse, TradeUpdate

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("/", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[TradeStatus] = None,
    symbol: Optional[str] = None,
    market_type: Optional[str] = None,
    direction: Optional[TradeDirection] = None,
    trading_mode: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List trades with optional filters."""
    query = select(Trade).order_by(desc(Trade.created_at))

    if status:
        query = query.where(Trade.status == status)
    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
    if market_type:
        query = query.where(Trade.market_type == market_type)
    if direction:
        query = query.where(Trade.direction == direction)
    if trading_mode:
        query = query.where(Trade.trading_mode == trading_mode)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/open", response_model=List[TradeResponse])
async def get_open_trades(db: AsyncSession = Depends(get_db)):
    """Get all currently open trades."""
    result = await db.execute(
        select(Trade)
        .where(Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL]))
        .order_by(desc(Trade.opened_at))
    )
    return result.scalars().all()


@router.get("/today", response_model=List[TradeResponse])
async def get_todays_trades(db: AsyncSession = Depends(get_db)):
    """Get trades opened today."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Trade)
        .where(Trade.created_at >= today_start)
        .order_by(desc(Trade.created_at))
    )
    return result.scalars().all()


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific trade by ID."""
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/stats/summary")
async def get_trade_stats(
    days: int = Query(30, ge=1, le=365),
    market_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated trade statistics."""
    since = datetime.utcnow() - timedelta(days=days)
    query = (
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
    )
    if market_type:
        query = query.where(Trade.market_type == market_type)

    result = await db.execute(query)
    trades = result.scalars().all()

    if not trades:
        return {
            "period_days": days,
            "total_trades": 0,
            "message": "No closed trades in period",
        }

    total = len(trades)
    winners = [t for t in trades if (t.pnl or 0) > 0]
    losers = [t for t in trades if (t.pnl or 0) <= 0]
    total_pnl = sum(t.pnl or 0 for t in trades)
    win_pnl = sum(t.pnl or 0 for t in winners)
    loss_pnl = abs(sum(t.pnl or 0 for t in losers))
    win_rate = len(winners) / total if total > 0 else 0.0
    profit_factor = win_pnl / loss_pnl if loss_pnl > 0 else float("inf")

    avg_conf = sum(t.ai_confidence or 0 for t in trades) / total

    # By session
    session_stats = {}
    for t in trades:
        s = t.session or "unknown"
        if s not in session_stats:
            session_stats[s] = {"count": 0, "pnl": 0.0}
        session_stats[s]["count"] += 1
        session_stats[s]["pnl"] += t.pnl or 0

    return {
        "period_days": days,
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": round(win_rate, 4),
        "win_rate_pct": f"{win_rate * 100:.1f}%",
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(win_pnl / len(winners), 2) if winners else 0,
        "avg_loss": round(-loss_pnl / len(losers), 2) if losers else 0,
        "profit_factor": round(profit_factor, 2),
        "avg_ai_confidence": round(avg_conf, 4),
        "by_session": session_stats,
    }
