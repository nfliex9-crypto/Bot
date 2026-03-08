from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select

from app.core.config import get_settings
from app.db.init_db import ensure_bot_state
from app.db.models import SignalRecord, TradeRecord
from app.db.session import db_session
from app.services.ai import RandomForestConfidenceModel


router = APIRouter()


class ToggleResponse(BaseModel):
    trading_enabled: bool


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/status")
def status() -> dict[str, object]:
    with db_session() as session:
        state = ensure_bot_state(session)
        return {
            "trading_enabled": state.trading_enabled,
            "current_equity": state.current_equity,
            "peak_equity": state.peak_equity,
            "current_drawdown": state.current_drawdown,
            "open_positions": state.open_positions,
            "last_cycle_at": state.last_cycle_at,
            "notes": state.notes,
        }


@router.post("/bot/enable", response_model=ToggleResponse)
def enable_bot() -> ToggleResponse:
    with db_session() as session:
        state = ensure_bot_state(session)
        state.trading_enabled = True
        state.notes = None
        return ToggleResponse(trading_enabled=True)


@router.post("/bot/disable", response_model=ToggleResponse)
def disable_bot() -> ToggleResponse:
    with db_session() as session:
        state = ensure_bot_state(session)
        state.trading_enabled = False
        state.notes = "disabled_by_operator"
        return ToggleResponse(trading_enabled=False)


@router.get("/trades")
def list_trades(limit: int = 50) -> list[dict[str, object]]:
    with db_session() as session:
        trades = session.scalars(select(TradeRecord).order_by(desc(TradeRecord.created_at)).limit(limit)).all()
        return [
            {
                "id": trade.id,
                "market": trade.market,
                "symbol": trade.symbol,
                "mode": trade.mode,
                "direction": trade.direction,
                "status": trade.status,
                "entry_price": trade.entry_price,
                "executed_price": trade.executed_price,
                "remaining_quantity": trade.remaining_quantity,
                "realized_pnl": trade.realized_pnl,
                "unrealized_pnl": trade.unrealized_pnl,
                "confidence": trade.confidence,
                "opened_at": trade.opened_at,
                "closed_at": trade.closed_at,
                "details": trade.details,
            }
            for trade in trades
        ]


@router.get("/signals")
def list_signals(limit: int = 50) -> list[dict[str, object]]:
    with db_session() as session:
        signals = session.scalars(select(SignalRecord).order_by(desc(SignalRecord.created_at)).limit(limit)).all()
        return [
            {
                "id": signal.id,
                "market": signal.market,
                "symbol": signal.symbol,
                "direction": signal.direction,
                "status": signal.status,
                "confidence": signal.confidence,
                "passed_filters": signal.passed_filters,
                "blocked_reason": signal.blocked_reason,
                "payload": signal.payload,
                "created_at": signal.created_at,
            }
            for signal in signals
        ]


@router.post("/ai/train")
def train_model() -> dict[str, object]:
    settings = get_settings()
    model = RandomForestConfidenceModel(settings)
    with db_session() as session:
        trades = session.scalars(select(TradeRecord).order_by(TradeRecord.created_at)).all()
        rows = [
            {
                "feature_vector": trade.feature_vector,
                "realized_pnl": trade.realized_pnl,
                "status": trade.status,
            }
            for trade in trades
        ]
    try:
        return model.train(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
