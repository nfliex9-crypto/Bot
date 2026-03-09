"""
Monitoring API Routes.

Exposes:
  GET /monitoring/metrics     – live runtime metrics snapshot
  GET /monitoring/status      – detailed system status
  GET /monitoring/performance – performance tracker output
  GET /monitoring/healthcheck – full component health probe
  GET /monitoring/guards      – risk guard status
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.trade import Trade, TradeStatus
from app.monitoring.metrics import get_metrics
from app.monitoring.healthcheck import HealthChecker
from app.monitoring.performance_tracker import PerformanceTracker
from app.bot.trading_bot import get_bot
from app.config import settings

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

_health_checker = HealthChecker()
_perf_tracker = PerformanceTracker()


@router.get("/metrics")
async def live_metrics():
    """Live runtime metrics: P&L, win rate, latency, slippage, spread."""
    return get_metrics().snapshot()


@router.get("/status")
async def system_status():
    """Detailed system status including bot state, session, risk guard."""
    bot = get_bot()
    metrics = get_metrics()
    snap = metrics.snapshot()

    guard_status = {}
    if bot.risk_manager:
        guard_status = bot.risk_manager.get_account_stats()

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "bot": bot.get_status(),
        "metrics": snap,
        "risk": guard_status,
        "config": {
            "trading_mode": settings.TRADING_MODE.value,
            "risk_per_trade_pct": f"{settings.RISK_PER_TRADE * 100:.2f}%",
            "max_drawdown_pct": f"{settings.MAX_DRAWDOWN * 100:.1f}%",
            "min_ai_confidence": settings.MIN_CONFIDENCE,
            "scan_interval_s": settings.SCAN_INTERVAL_SECONDS,
        },
    }


@router.get("/performance")
async def performance_report(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Full performance report via PerformanceTracker."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
        .order_by(Trade.closed_at)
    )
    trades = result.scalars().all()
    trade_dicts = [
        {
            "pnl": t.pnl or 0.0,
            "symbol": t.symbol,
            "direction": t.direction.value if t.direction else None,
            "session": t.session,
            "ai_confidence": t.ai_confidence,
            "risk_reward_ratio": t.risk_reward_ratio,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        }
        for t in trades
    ]

    report = _perf_tracker.compute(trade_dicts, f"{days}d")
    equity = _perf_tracker.equity_curve(trade_dicts)
    rolling_7d = _perf_tracker.rolling_window(trade_dicts, 7)
    rolling_30d = _perf_tracker.rolling_window(trade_dicts, 30)

    return {
        "period_days": days,
        "all_time": report,
        "rolling_7d": rolling_7d,
        "rolling_30d": rolling_30d,
        "equity_curve": equity[-50:],  # last 50 points
    }


@router.get("/healthcheck")
async def healthcheck():
    """Full component health probe."""
    bot = get_bot()
    result = await _health_checker.run_all(
        db_url=settings.DATABASE_URL,
        redis_url=settings.REDIS_URL,
        mt5_connected=bot.mt5_broker.is_connected if bot.mt5_broker else False,
        binance_connected=bot.binance_broker.is_connected if bot.binance_broker else False,
        bot_state=bot.state,
    )
    return result


@router.get("/guards")
async def risk_guards_status():
    """Current state of all risk guards."""
    bot = get_bot()
    if not hasattr(bot, "_risk_guard") or bot._risk_guard is None:
        return {"message": "Risk guards not initialized", "guards": {}}
    return bot._risk_guard.status() if hasattr(bot, "_risk_guard") else {}
