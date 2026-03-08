from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from src.models.database import (
    Trade, PerformanceSnapshot, NewsEvent, TradeStatus, get_db
)
from src.api.schemas import PerformanceResponse, NewsEventResponse
from src.filters.news_filter import NewsFilter

router = APIRouter(prefix="/performance", tags=["Performance"])
news_filter = NewsFilter()


@router.get("/", response_model=PerformanceResponse)
async def get_performance(db: AsyncSession = Depends(get_db)):
    """Get current account performance metrics."""
    from src.bot.orchestrator import get_orchestrator
    orch = get_orchestrator()

    if orch and orch.risk_manager:
        risk_status = orch.risk_manager.get_status()
        balance = risk_status["current_balance"]
        equity = balance
        session_trades = risk_status["session_trades"]
        drawdown_pct = risk_status["current_drawdown_pct"]
    else:
        from config.settings import settings
        balance = settings.account_balance
        equity = settings.account_balance
        session_trades = 0
        drawdown_pct = 0.0

    result = await db.execute(
        select(Trade).where(Trade.status == TradeStatus.CLOSED)
    )
    closed_trades = result.scalars().all()

    total = len(closed_trades)
    winners = [t for t in closed_trades if float(t.realized_pnl) > 0]
    losers = [t for t in closed_trades if float(t.realized_pnl) <= 0]
    total_pnl = sum(float(t.realized_pnl) for t in closed_trades)
    gross_profit = sum(float(t.realized_pnl) for t in winners)
    gross_loss = abs(sum(float(t.realized_pnl) for t in losers))

    win_rate = len(winners) / total if total > 0 else None
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    result_open = await db.execute(
        select(Trade).where(
            Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL_CLOSE])
        )
    )
    open_trades = result_open.scalars().all()

    return PerformanceResponse(
        balance=balance,
        equity=equity,
        open_trades=len(open_trades),
        total_trades=total,
        winning_trades=len(winners),
        losing_trades=len(losers),
        total_pnl=round(total_pnl, 2),
        win_rate=round(win_rate, 4) if win_rate is not None else None,
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        max_drawdown=round(drawdown_pct * balance, 2),
        session_trades=session_trades,
        current_drawdown_pct=round(drawdown_pct, 4),
    )


@router.get("/equity_curve")
async def get_equity_curve(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get equity curve data points."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.snapshot_time >= since)
        .order_by(PerformanceSnapshot.snapshot_time)
    )
    snapshots = result.scalars().all()
    return [
        {
            "time": s.snapshot_time.isoformat(),
            "balance": float(s.balance),
            "equity": float(s.equity),
            "total_pnl": float(s.total_pnl),
        }
        for s in snapshots
    ]


@router.get("/by_symbol")
async def get_performance_by_symbol(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get P&L breakdown by symbol."""
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Trade).where(
            Trade.status == TradeStatus.CLOSED,
            Trade.close_time >= since,
        )
    )
    trades = result.scalars().all()

    by_symbol = {}
    for trade in trades:
        sym = trade.symbol
        if sym not in by_symbol:
            by_symbol[sym] = {"symbol": sym, "trades": 0, "wins": 0, "pnl": 0.0}
        by_symbol[sym]["trades"] += 1
        pnl = float(trade.realized_pnl)
        if pnl > 0:
            by_symbol[sym]["wins"] += 1
        by_symbol[sym]["pnl"] += pnl

    for sym in by_symbol:
        t = by_symbol[sym]["trades"]
        w = by_symbol[sym]["wins"]
        by_symbol[sym]["win_rate"] = round(w / t, 4) if t > 0 else 0
        by_symbol[sym]["pnl"] = round(by_symbol[sym]["pnl"], 2)

    return sorted(by_symbol.values(), key=lambda x: x["pnl"], reverse=True)


@router.get("/news", response_model=List[dict])
async def get_upcoming_news():
    """Get upcoming high-impact news events."""
    return news_filter.get_upcoming_events(hours_ahead=8)
