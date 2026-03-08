from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AIModelResponse,
    HealthResponse,
    PerformanceResponse,
    SignalResponse,
    StatusResponse,
    TradeResponse,
)
from app.core.database import get_async_session
from app.models.signal import Signal
from app.models.trade import Trade, TradeStatus

router = APIRouter()

# These are set by the bot orchestrator at startup
_bot_ref = None


def set_bot_reference(bot) -> None:
    global _bot_ref
    _bot_ref = bot


def _get_bot():
    if _bot_ref is None:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return _bot_ref


# ── Health ──────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="running",
        database="connected",
        mt5_connected=False,
        binance_connected=False,
        timestamp=datetime.now(timezone.utc),
    )


# ── Status ──────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status():
    bot = _get_bot()
    risk = bot.risk_manager
    session = bot.session_filter.get_session_info()

    return StatusResponse(
        status="running" if bot.is_running else "stopped",
        mode=bot.settings.trading_mode.value,
        uptime_seconds=bot.uptime_seconds,
        balance=risk._current_balance,
        equity=risk._current_balance,
        open_trades=risk._open_trade_count,
        session_trades=risk._session_trade_count,
        drawdown_pct=risk.current_drawdown_pct * 100,
        current_session=session,
    )


# ── Trades ──────────────────────────────────────────────────

@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    status: str | None = None,
    limit: int = Query(default=50, le=500),
    session: AsyncSession = Depends(get_async_session),
):
    q = select(Trade).order_by(desc(Trade.opened_at)).limit(limit)
    if status:
        q = q.where(Trade.status == status)
    result = await session.execute(q)
    trades = result.scalars().all()
    return [
        TradeResponse(
            id=t.id,
            symbol=t.symbol,
            market=t.market,
            side=t.side,
            status=t.status,
            entry_price=t.entry_price,
            stop_loss=t.stop_loss,
            tp1=t.tp1,
            tp2=t.tp2,
            tp3=t.tp3,
            quantity=t.quantity,
            confidence=t.confidence,
            pnl=t.pnl,
            is_paper=t.is_paper,
            opened_at=t.opened_at,
            closed_at=t.closed_at,
        )
        for t in trades
    ]


# ── Signals ─────────────────────────────────────────────────

@router.get("/signals", response_model=List[SignalResponse])
async def get_signals(
    limit: int = Query(default=50, le=500),
    session: AsyncSession = Depends(get_async_session),
):
    q = select(Signal).order_by(desc(Signal.created_at)).limit(limit)
    result = await session.execute(q)
    signals = result.scalars().all()
    return [
        SignalResponse(
            id=s.id,
            symbol=s.symbol,
            direction=s.direction,
            confidence=s.confidence,
            entry_price=s.entry_price,
            stop_loss=s.stop_loss,
            tp1=s.tp1,
            tp2=s.tp2,
            tp3=s.tp3,
            created_at=s.created_at,
        )
        for s in signals
    ]


# ── Performance ─────────────────────────────────────────────

@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    session: AsyncSession = Depends(get_async_session),
):
    closed_q = select(Trade).where(Trade.status == TradeStatus.CLOSED.value)
    result = await session.execute(closed_q)
    trades = result.scalars().all()

    if not trades:
        return PerformanceResponse(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, total_pnl=0, avg_pnl=0, max_drawdown=0,
            profit_factor=0, avg_rr=0, best_trade=0, worst_trade=0,
        )

    pnls = [t.pnl or 0.0 for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)

    gross_profit = sum(winners) if winners else 0
    gross_loss = abs(sum(losers)) if losers else 0

    # Running drawdown
    equity_curve = []
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        running += p
        equity_curve.append(running)
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd

    return PerformanceResponse(
        total_trades=len(trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=len(winners) / len(trades) * 100 if trades else 0,
        total_pnl=total_pnl,
        avg_pnl=total_pnl / len(trades) if trades else 0,
        max_drawdown=max_dd,
        profit_factor=gross_profit / gross_loss if gross_loss else 0,
        avg_rr=0,
        best_trade=max(pnls) if pnls else 0,
        worst_trade=min(pnls) if pnls else 0,
    )


# ── AI Model ────────────────────────────────────────────────

@router.get("/ai/model", response_model=AIModelResponse)
async def get_ai_model():
    bot = _get_bot()
    clf = bot.classifier
    return AIModelResponse(
        model_loaded=clf._model is not None,
        feature_importance=clf.get_feature_importance(),
        min_confidence=clf._min_confidence,
        total_predictions=0,
    )


# ── Controls ────────────────────────────────────────────────

@router.post("/bot/start")
async def start_bot():
    bot = _get_bot()
    if bot.is_running:
        return {"message": "Bot already running"}
    bot.start()
    return {"message": "Bot started"}


@router.post("/bot/stop")
async def stop_bot():
    bot = _get_bot()
    if not bot.is_running:
        return {"message": "Bot already stopped"}
    await bot.stop()
    return {"message": "Bot stopped"}


@router.post("/bot/reset-session")
async def reset_session():
    bot = _get_bot()
    bot.risk_manager.reset_session()
    return {"message": "Session reset"}
