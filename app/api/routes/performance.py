"""
Performance Analytics API Routes.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional
from datetime import datetime, timedelta, date

from app.database import get_db
from app.models.trade import Trade, TradeStatus
from app.models.signal import Signal
from app.bot.trading_bot import get_bot

router = APIRouter(prefix="/performance", tags=["Performance"])


@router.get("/summary")
async def get_performance_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive performance summary."""
    since = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
        .order_by(Trade.closed_at)
    )
    trades = result.scalars().all()

    if not trades:
        return {"period_days": days, "message": "No completed trades"}

    pnls = [t.pnl or 0.0 for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    total_pnl = sum(pnls)
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))
    win_rate = len(winners) / len(pnls)

    # Max drawdown calculation
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / (peak + 1e-10) if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (simplified, daily)
    import numpy as np
    pnl_arr = np.array(pnls)
    sharpe = (pnl_arr.mean() / (pnl_arr.std() + 1e-10)) * np.sqrt(252) if len(pnl_arr) > 1 else 0.0

    # Average RR
    rr_values = [t.risk_reward_ratio for t in trades if t.risk_reward_ratio]
    avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0

    # Consecutive stats
    max_consec_wins, max_consec_losses = _calc_consecutive(pnls)

    # By direction
    longs = [t for t in trades if t.direction and "long" in str(t.direction).lower()]
    shorts = [t for t in trades if t.direction and "short" in str(t.direction).lower()]

    return {
        "period_days": days,
        "total_closed_trades": len(trades),
        "total_pnl": round(total_pnl, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "win_rate": round(win_rate, 4),
        "win_rate_pct": f"{win_rate * 100:.1f}%",
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else "∞",
        "avg_win": round(sum(winners) / len(winners), 2) if winners else 0,
        "avg_loss": round(sum(losers) / len(losers), 2) if losers else 0,
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_pct": f"{max_dd * 100:.1f}%",
        "sharpe_ratio": round(float(sharpe), 3),
        "avg_rr": round(avg_rr, 2),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "by_direction": {
            "long": {
                "count": len(longs),
                "win_rate": round(
                    len([t for t in longs if (t.pnl or 0) > 0]) / max(len(longs), 1), 4
                ),
                "total_pnl": round(sum(t.pnl or 0 for t in longs), 2),
            },
            "short": {
                "count": len(shorts),
                "win_rate": round(
                    len([t for t in shorts if (t.pnl or 0) > 0]) / max(len(shorts), 1), 4
                ),
                "total_pnl": round(sum(t.pnl or 0 for t in shorts), 2),
            },
        },
    }


@router.get("/equity-curve")
async def get_equity_curve(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get equity curve data for charting."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
        .order_by(Trade.closed_at)
    )
    trades = result.scalars().all()

    equity = settings_balance = 3000.0
    curve = []
    for t in trades:
        equity += (t.pnl or 0.0)
        curve.append({
            "date": t.closed_at.isoformat() if t.closed_at else None,
            "equity": round(equity, 2),
            "pnl": round(t.pnl or 0.0, 2),
            "symbol": t.symbol,
        })

    return {"data": curve, "start_balance": settings_balance, "end_balance": round(equity, 2)}


@router.get("/by-session")
async def get_performance_by_session(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Performance breakdown by trading session."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
    )
    trades = result.scalars().all()

    sessions = {}
    for t in trades:
        s = t.session or "unknown"
        if s not in sessions:
            sessions[s] = {"trades": 0, "wins": 0, "pnl": 0.0}
        sessions[s]["trades"] += 1
        if (t.pnl or 0) > 0:
            sessions[s]["wins"] += 1
        sessions[s]["pnl"] += t.pnl or 0.0

    for s in sessions:
        n = sessions[s]["trades"]
        sessions[s]["win_rate"] = round(sessions[s]["wins"] / n, 4) if n > 0 else 0.0
        sessions[s]["pnl"] = round(sessions[s]["pnl"], 2)

    return {"period_days": days, "sessions": sessions}


@router.get("/risk-metrics")
async def get_risk_metrics():
    """Get current risk metrics from the bot."""
    bot = get_bot()
    if bot.risk_manager:
        return bot.risk_manager.get_account_stats()
    return {"message": "Bot not running"}


def _calc_consecutive(pnls):
    """Calculate max consecutive wins and losses."""
    max_wins = max_losses = cur_wins = cur_losses = 0
    for p in pnls:
        if p > 0:
            cur_wins += 1
            cur_losses = 0
            max_wins = max(max_wins, cur_wins)
        else:
            cur_losses += 1
            cur_wins = 0
            max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses
