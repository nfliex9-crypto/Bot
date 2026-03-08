from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from database.connection import get_db_session
from database.models import AccountSnapshot, SignalLog, TradeRecord
from filters.news_filter import news_filter
from filters.session_filter import session_filter

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


class EquityCurvePoint(BaseModel):
    timestamp: datetime
    balance: float
    equity: float
    drawdown_pct: float


class DailyPerformance(BaseModel):
    date: str
    trades: int
    wins: int
    losses: int
    pnl: float
    win_rate: float


class NewsEventResponse(BaseModel):
    time: str
    currency: str
    impact: str
    title: str


class DashboardSummary(BaseModel):
    session: str
    tradeable: bool
    minutes_to_session: int
    todays_news: List[NewsEventResponse]
    account_balance: float
    account_equity: float
    drawdown_pct: float
    total_closed_trades: int
    win_rate_30d: float
    pnl_30d: float
    open_trades_count: int
    ai_signals_today: int
    executed_today: int


@router.get("/summary", response_model=DashboardSummary)
async def get_summary():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days = now - timedelta(days=30)

    async with get_db_session() as sess:
        # Latest account snapshot
        snap_result = await sess.execute(
            select(AccountSnapshot).order_by(desc(AccountSnapshot.timestamp)).limit(1)
        )
        snap = snap_result.scalar_one_or_none()

        # 30-day trade stats
        trades_result = await sess.execute(
            select(TradeRecord).where(
                TradeRecord.opened_at >= thirty_days,
                TradeRecord.status == "closed",
            )
        )
        closed_trades = trades_result.scalars().all()

        # Today's signals
        signals_result = await sess.execute(
            select(func.count(SignalLog.id)).where(SignalLog.timestamp >= today_start)
        )
        signals_today = signals_result.scalar() or 0

        executed_result = await sess.execute(
            select(func.count(SignalLog.id)).where(
                SignalLog.timestamp >= today_start, SignalLog.executed.is_(True)
            )
        )
        executed_today = executed_result.scalar() or 0

        open_count_result = await sess.execute(
            select(func.count(TradeRecord.id)).where(TradeRecord.status == "open")
        )
        open_count = open_count_result.scalar() or 0

    winners = [t for t in closed_trades if (t.pnl or 0) > 0]
    pnl_30d = sum((t.pnl or 0) for t in closed_trades)
    win_rate = len(winners) / len(closed_trades) if closed_trades else 0.0

    current_session = session_filter.current_session()
    tradeable = session_filter.is_tradeable("EURUSD")

    return DashboardSummary(
        session=current_session.value,
        tradeable=tradeable,
        minutes_to_session=session_filter.minutes_to_session_open(),
        todays_news=[
            NewsEventResponse(**e)
            for e in news_filter.get_todays_events()
        ],
        account_balance=snap.balance if snap else 3000.0,
        account_equity=snap.equity if snap else 3000.0,
        drawdown_pct=snap.drawdown_pct if snap else 0.0,
        total_closed_trades=len(closed_trades),
        win_rate_30d=round(win_rate, 4),
        pnl_30d=round(pnl_30d, 2),
        open_trades_count=open_count,
        ai_signals_today=signals_today,
        executed_today=executed_today,
    )


@router.get("/equity-curve", response_model=List[EquityCurvePoint])
async def get_equity_curve(
    days: int = Query(7, description="Number of days to include"),
    interval_minutes: int = Query(60),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_db_session() as sess:
        result = await sess.execute(
            select(AccountSnapshot)
            .where(AccountSnapshot.timestamp >= since)
            .order_by(AccountSnapshot.timestamp)
        )
        snaps = result.scalars().all()

    # Downsample to avoid large payloads
    step = max(1, interval_minutes)
    sampled = []
    last_ts = None
    for s in snaps:
        if last_ts is None or (s.timestamp - last_ts).total_seconds() >= step * 60:
            sampled.append(
                EquityCurvePoint(
                    timestamp=s.timestamp,
                    balance=s.balance,
                    equity=s.equity,
                    drawdown_pct=s.drawdown_pct,
                )
            )
            last_ts = s.timestamp
    return sampled


@router.get("/daily-performance", response_model=List[DailyPerformance])
async def get_daily_performance(days: int = Query(30)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_db_session() as sess:
        result = await sess.execute(
            select(TradeRecord).where(
                TradeRecord.closed_at.isnot(None),
                TradeRecord.closed_at >= since,
                TradeRecord.status == "closed",
            ).order_by(TradeRecord.closed_at)
        )
        trades = result.scalars().all()

    daily: Dict[str, Dict] = {}
    for t in trades:
        if t.closed_at is None:
            continue
        date_key = t.closed_at.strftime("%Y-%m-%d")
        if date_key not in daily:
            daily[date_key] = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        daily[date_key]["trades"] += 1
        daily[date_key]["pnl"] += t.pnl or 0
        if (t.pnl or 0) > 0:
            daily[date_key]["wins"] += 1
        else:
            daily[date_key]["losses"] += 1

    return [
        DailyPerformance(
            date=date,
            trades=d["trades"],
            wins=d["wins"],
            losses=d["losses"],
            pnl=round(d["pnl"], 2),
            win_rate=round(d["wins"] / d["trades"], 4) if d["trades"] else 0.0,
        )
        for date, d in sorted(daily.items())
    ]
