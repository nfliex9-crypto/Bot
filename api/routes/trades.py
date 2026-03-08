from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select

from database.connection import get_db_session
from database.models import SignalLog, TradeRecord

router = APIRouter(prefix="/trades", tags=["Trades"])


# ─── Response Schemas ─────────────────────────────────────────────────────────

class TradeResponse(BaseModel):
    trade_id: str
    symbol: str
    market: str
    direction: str
    status: str
    mode: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_amount: float
    risk_reward: float
    atr_value: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None
    ai_confidence: float
    session: str
    breakeven_moved: bool
    tp1_hit: bool
    tp2_hit: bool
    tp3_hit: bool
    opened_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SignalResponse(BaseModel):
    id: int
    timestamp: datetime
    symbol: str
    market: str
    direction: str
    h1_bias: str
    m15_structure: str
    bos_confirmed: bool
    sweep_confirmed: bool
    pullback_valid: bool
    ai_confidence: float
    executed: bool
    rejected_reason: Optional[str] = None

    class Config:
        from_attributes = True


class TradeStatsResponse(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_rr: float
    best_trade: float
    worst_trade: float
    avg_confidence: float


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[TradeResponse])
async def list_trades(
    status: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
):
    async with get_db_session() as session:
        q = select(TradeRecord).order_by(desc(TradeRecord.opened_at))
        if status:
            q = q.where(TradeRecord.status == status)
        if market:
            q = q.where(TradeRecord.market == market)
        if symbol:
            q = q.where(TradeRecord.symbol == symbol.upper())
        q = q.limit(limit).offset(offset)
        result = await session.execute(q)
        return result.scalars().all()


@router.get("/stats", response_model=TradeStatsResponse)
async def get_trade_stats(
    days: int = Query(30, description="Number of days to include"),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_db_session() as session:
        q = select(TradeRecord).where(TradeRecord.opened_at >= since)
        result = await session.execute(q)
        trades = result.scalars().all()

    total = len(trades)
    open_t = sum(1 for t in trades if t.status == "open")
    closed_t = [t for t in trades if t.status == "closed"]
    winners = [t for t in closed_t if (t.pnl or 0) > 0]
    losers = [t for t in closed_t if (t.pnl or 0) <= 0]
    pnls = [t.pnl for t in closed_t if t.pnl is not None]
    confidences = [t.ai_confidence for t in trades]

    return TradeStatsResponse(
        total_trades=total,
        open_trades=open_t,
        closed_trades=len(closed_t),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=len(winners) / len(closed_t) if closed_t else 0.0,
        total_pnl=sum(pnls),
        avg_pnl=sum(pnls) / len(pnls) if pnls else 0.0,
        avg_rr=sum(t.risk_reward for t in closed_t) / len(closed_t) if closed_t else 0.0,
        best_trade=max(pnls) if pnls else 0.0,
        worst_trade=min(pnls) if pnls else 0.0,
        avg_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
    )


@router.get("/signals", response_model=List[SignalResponse])
async def list_signals(
    executed: Optional[bool] = Query(None),
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
):
    async with get_db_session() as session:
        q = select(SignalLog).order_by(desc(SignalLog.timestamp)).limit(limit)
        if executed is not None:
            q = q.where(SignalLog.executed == executed)
        if symbol:
            q = q.where(SignalLog.symbol == symbol.upper())
        result = await session.execute(q)
        return result.scalars().all()


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade(trade_id: str):
    async with get_db_session() as session:
        result = await session.execute(
            select(TradeRecord).where(TradeRecord.trade_id == trade_id)
        )
        trade = result.scalar_one_or_none()
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        return trade
