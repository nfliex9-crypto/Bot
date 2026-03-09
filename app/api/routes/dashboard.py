"""
Dashboard API Routes.

Provides structured JSON endpoints for the trading dashboard frontend.
All data is designed to be consumed directly by charting libraries
(e.g. Chart.js, Recharts, ApexCharts).

Routes:
  GET /dashboard/equity         – equity curve + drawdown overlay
  GET /dashboard/trades         – recent + open trades with enriched fields
  GET /dashboard/signals        – signal feed with AI scores
  GET /dashboard/ai_scores      – confidence histogram + feature importances
  GET /dashboard/overview       – single-call summary for dashboard home
  GET /dashboard/metrics        – live execution metrics (latency, slippage, spread)
  GET /dashboard/sessions       – P&L heatmap by session
  GET /dashboard/symbols        – per-symbol performance table
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models.trade import Trade, TradeStatus, TradeDirection
from app.models.signal import Signal, SignalStatus
from app.monitoring.metrics import get_metrics
from app.monitoring.performance_tracker import PerformanceTracker
from app.bot.trading_bot import get_bot
from app.config import settings

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

UTC = timezone.utc
_tracker = PerformanceTracker()


# ── Helpers ────────────────────────────────────────────────────────────────

def _trade_to_dict(t: Trade) -> dict:
    return {
        "id": t.id,
        "ticket": t.ticket,
        "symbol": t.symbol,
        "market_type": t.market_type,
        "direction": t.direction.value if t.direction else None,
        "status": t.status.value if t.status else None,
        "trading_mode": t.trading_mode,
        "entry_price": t.entry_price,
        "current_price": t.current_price,
        "exit_price": t.exit_price,
        "lot_size": t.lot_size,
        "stop_loss": t.stop_loss,
        "take_profit_1": t.take_profit_1,
        "take_profit_2": t.take_profit_2,
        "take_profit_3": t.take_profit_3,
        "pnl": t.pnl,
        "ai_confidence": t.ai_confidence,
        "session": t.session,
        "strategy": t.strategy,
        "tp1_hit": t.tp1_hit,
        "tp2_hit": t.tp2_hit,
        "tp3_hit": t.tp3_hit,
        "breakeven_moved": t.breakeven_moved,
        "risk_amount": t.risk_amount,
        "risk_reward_ratio": t.risk_reward_ratio,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _signal_to_dict(s: Signal) -> dict:
    return {
        "id": s.id,
        "symbol": s.symbol,
        "market_type": s.market_type,
        "direction": s.direction,
        "status": s.status.value if s.status else None,
        "entry_price": s.entry_price,
        "stop_loss": s.stop_loss,
        "take_profit_1": s.take_profit_1,
        "take_profit_2": s.take_profit_2,
        "take_profit_3": s.take_profit_3,
        "atr": s.atr,
        "h1_bias": s.h1_bias,
        "m15_trend": s.m15_trend,
        "m5_signal": s.m5_signal,
        "liquidity_sweep_detected": s.liquidity_sweep_detected,
        "bos_detected": s.bos_detected,
        "pullback_entry": s.pullback_entry,
        "ai_confidence": s.ai_confidence,
        "session": s.session,
        "news_clear": s.news_clear,
        "risk_reward": s.risk_reward,
        "rejection_reason": s.rejection_reason,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "executed_at": s.executed_at.isoformat() if s.executed_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/overview")
async def dashboard_overview(db: AsyncSession = Depends(get_db)):
    """
    Single-call dashboard home data: bot status, risk metrics,
    today's P&L, session info, and recent signals.
    """
    bot = get_bot()
    metrics = get_metrics()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_trades_result = await db.execute(
        select(Trade).where(Trade.created_at >= today_start)
    )
    today_trades = today_trades_result.scalars().all()
    today_pnl = sum(t.pnl or 0 for t in today_trades if t.status == TradeStatus.CLOSED)
    today_open = [t for t in today_trades if t.status in (TradeStatus.OPEN, TradeStatus.PARTIAL)]

    recent_signals_result = await db.execute(
        select(Signal)
        .where(Signal.created_at >= datetime.utcnow() - timedelta(hours=4))
        .order_by(desc(Signal.created_at))
        .limit(10)
    )
    recent_signals = recent_signals_result.scalars().all()

    bot_status = bot.get_status()
    metrics_snap = metrics.snapshot()

    return {
        "bot": {
            "state": bot_status["state"],
            "trading_mode": bot_status["trading_mode"],
            "uptime": bot_status.get("uptime"),
            "session": bot_status.get("session"),
            "session_active": bot_status.get("session_active"),
        },
        "today": {
            "pnl": round(today_pnl, 2),
            "trades": len(today_trades),
            "open_trades": len(today_open),
        },
        "risk": bot_status.get("risk", {}),
        "metrics": metrics_snap,
        "recent_signals": [_signal_to_dict(s) for s in recent_signals],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/equity")
async def dashboard_equity(
    days: int = Query(30, ge=1, le=365),
    initial_balance: float = Query(3000.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Equity curve data suitable for a line chart.
    Returns equity, drawdown overlay, and summary stats.
    """
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
        .order_by(Trade.closed_at)
    )
    trades = result.scalars().all()
    trade_dicts = [_trade_to_dict(t) for t in trades]

    curve = _tracker.equity_curve(trade_dicts, initial_balance)
    metrics = _tracker.compute(trade_dicts, f"{days}d")

    # Daily aggregation for bar chart overlay
    daily: dict = {}
    for point in curve:
        date_str = (point.get("date") or "")[:10]
        if date_str:
            daily[date_str] = daily.get(date_str, 0.0) + float(point.get("pnl", 0))

    return {
        "period_days": days,
        "initial_balance": initial_balance,
        "final_equity": curve[-1]["equity"] if curve else initial_balance,
        "curve": curve,
        "daily_pnl": [{"date": k, "pnl": round(v, 2)} for k, v in sorted(daily.items())],
        "summary": metrics,
    }


@router.get("/trades")
async def dashboard_trades(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Enriched trade list for the trades table / timeline view.
    """
    query = select(Trade).order_by(desc(Trade.created_at))
    if status:
        try:
            query = query.where(Trade.status == TradeStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.where(Trade.created_at >= since)
    query = query.limit(limit)

    result = await db.execute(query)
    trades = result.scalars().all()

    open_result = await db.execute(
        select(Trade).where(Trade.status.in_([TradeStatus.OPEN, TradeStatus.PARTIAL]))
    )
    open_trades = open_result.scalars().all()

    return {
        "open_trades": [_trade_to_dict(t) for t in open_trades],
        "recent_trades": [_trade_to_dict(t) for t in trades],
        "open_count": len(open_trades),
        "total_shown": len(trades),
    }


@router.get("/signals")
async def dashboard_signals(
    limit: int = Query(50, ge=1, le=200),
    hours: int = Query(24, ge=1, le=168),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Signal feed with AI confidence scores.
    Suitable for a real-time signal dashboard.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Signal)
        .where(Signal.created_at >= since)
        .where(Signal.ai_confidence >= min_confidence if min_confidence > 0 else True)
        .order_by(desc(Signal.created_at))
        .limit(limit)
    )
    signals = result.scalars().all()

    # Aggregate stats
    total = len(signals)
    executed = sum(1 for s in signals if s.status == SignalStatus.EXECUTED)
    rejected = sum(1 for s in signals if s.status == SignalStatus.REJECTED)
    avg_conf = sum(s.ai_confidence or 0 for s in signals) / max(total, 1)

    # Confidence distribution buckets
    buckets = {"0.0-0.5": 0, "0.5-0.6": 0, "0.6-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
    for s in signals:
        c = s.ai_confidence or 0
        if c < 0.5:   buckets["0.0-0.5"] += 1
        elif c < 0.6: buckets["0.5-0.6"] += 1
        elif c < 0.7: buckets["0.6-0.7"] += 1
        elif c < 0.8: buckets["0.7-0.8"] += 1
        elif c < 0.9: buckets["0.8-0.9"] += 1
        else:         buckets["0.9-1.0"] += 1

    return {
        "signals": [_signal_to_dict(s) for s in signals],
        "stats": {
            "total": total,
            "executed": executed,
            "rejected": rejected,
            "execution_rate": round(executed / max(total, 1), 4),
            "avg_confidence": round(avg_conf, 4),
        },
        "confidence_distribution": buckets,
        "period_hours": hours,
    }


@router.get("/ai_scores")
async def dashboard_ai_scores(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    AI model performance data:
    - Confidence vs outcome correlation
    - Feature importance (if model loaded)
    - Confidence threshold effectiveness
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Signals with their outcomes (matched to trades)
    sigs_result = await db.execute(
        select(Signal).where(Signal.created_at >= since)
    )
    signals = sigs_result.scalars().all()

    trades_result = await db.execute(
        select(Trade)
        .where(Trade.signal_id.isnot(None))
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.created_at >= since)
    )
    closed_trades = trades_result.scalars().all()
    trade_by_signal = {t.signal_id: t for t in closed_trades}

    # Build confidence vs outcome scatter data
    scatter = []
    for s in signals:
        if s.id in trade_by_signal:
            t = trade_by_signal[s.id]
            scatter.append({
                "signal_id": s.id,
                "symbol": s.symbol,
                "confidence": s.ai_confidence,
                "pnl": t.pnl,
                "outcome": "win" if (t.pnl or 0) > 0 else "loss",
                "direction": s.direction,
                "session": s.session,
            })

    # Threshold sensitivity (what win rate at each confidence level)
    thresholds = [0.5, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    threshold_analysis = []
    for thr in thresholds:
        filtered = [p for p in scatter if (p["confidence"] or 0) >= thr]
        wins = [p for p in filtered if p["outcome"] == "win"]
        threshold_analysis.append({
            "threshold": thr,
            "trades": len(filtered),
            "win_rate": round(len(wins) / max(len(filtered), 1), 4),
            "avg_pnl": round(sum(p["pnl"] for p in filtered) / max(len(filtered), 1), 2),
        })

    # Feature importances from loaded model
    feature_importance = {}
    try:
        from app.core.ai.model_registry import ModelRegistry
        registry = ModelRegistry()
        model = registry.get_active_model()
        if model and hasattr(model, "get_feature_importance"):
            feature_importance = dict(list(model.get_feature_importance().items())[:15])
    except Exception:
        pass

    return {
        "period_days": days,
        "scatter_data": scatter,
        "threshold_analysis": threshold_analysis,
        "feature_importance": feature_importance,
        "signals_total": len(signals),
        "signals_with_outcome": len(scatter),
    }


@router.get("/metrics")
async def dashboard_metrics():
    """
    Live execution metrics: latency, slippage, spread, scan rate.
    """
    m = get_metrics()
    return m.snapshot()


@router.get("/sessions")
async def dashboard_sessions(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    P&L heatmap by trading session for the last N days.
    """
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
    )
    trades = result.scalars().all()

    heatmap: dict = {}
    for t in trades:
        session = t.session or "unknown"
        date_str = t.closed_at.strftime("%Y-%m-%d") if t.closed_at else "unknown"
        key = (date_str, session)
        if key not in heatmap:
            heatmap[key] = {"pnl": 0.0, "trades": 0, "wins": 0}
        heatmap[key]["pnl"] += t.pnl or 0
        heatmap[key]["trades"] += 1
        if (t.pnl or 0) > 0:
            heatmap[key]["wins"] += 1

    return {
        "period_days": days,
        "heatmap": [
            {
                "date": k[0], "session": k[1],
                "pnl": round(v["pnl"], 2),
                "trades": v["trades"],
                "win_rate": round(v["wins"] / max(v["trades"], 1), 4),
            }
            for k, v in sorted(heatmap.items())
        ],
    }


@router.get("/symbols")
async def dashboard_symbols(
    days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
):
    """
    Per-symbol performance table.
    """
    since = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Trade)
        .where(Trade.status == TradeStatus.CLOSED)
        .where(Trade.closed_at >= since)
    )
    trades = result.scalars().all()
    trade_dicts = [_trade_to_dict(t) for t in trades]
    metrics = _tracker.compute(trade_dicts)

    return {
        "period_days": days,
        "symbols": metrics.get("breakdown", {}).get("by_symbol", {}),
    }
