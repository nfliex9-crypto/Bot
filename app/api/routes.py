from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.domain.models import EconomicEvent, TradingMode

router = APIRouter()


class ModeRequest(BaseModel):
    mode: TradingMode


class EconomicEventPayload(BaseModel):
    title: str
    currency: str
    impact: str = "high"
    starts_at: datetime
    source: str = "manual"


class TrainModelRequest(BaseModel):
    rows: list[dict[str, float | int]] = Field(default_factory=list)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/bot/status")
async def bot_status(request: Request) -> dict[str, object]:
    return request.app.state.engine.status()


@router.post("/bot/start")
async def start_bot(request: Request) -> dict[str, object]:
    state = request.app.state.repository.set_bot_enabled(True)
    return {"enabled": state.enabled, "mode": state.mode}


@router.post("/bot/stop")
async def stop_bot(request: Request) -> dict[str, object]:
    state = request.app.state.repository.set_bot_enabled(False)
    return {"enabled": state.enabled, "mode": state.mode}


@router.post("/bot/mode")
async def set_mode(payload: ModeRequest, request: Request) -> dict[str, str]:
    state = request.app.state.repository.set_bot_mode(payload.mode)
    return {"mode": state.mode}


@router.get("/trades")
async def list_trades(request: Request) -> list[dict[str, object]]:
    rows = request.app.state.repository.list_recent_trades()
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "market": row.market,
            "side": row.side,
            "mode": row.mode,
            "status": row.status,
            "entry_price": row.entry_price,
            "stop_loss": row.stop_loss,
            "tp1": row.take_profit_1,
            "tp2": row.take_profit_2,
            "tp3": row.take_profit_3,
            "confidence": row.confidence,
            "realized_pnl": row.realized_pnl,
            "created_at": row.created_at,
            "closed_at": row.closed_at,
        }
        for row in rows
    ]


@router.post("/news/events")
async def replace_news_events(payload: list[EconomicEventPayload], request: Request) -> dict[str, int]:
    events = [
        EconomicEvent(
            title=item.title,
            currency=item.currency.upper(),
            impact=item.impact.lower(),
            starts_at=item.starts_at if item.starts_at.tzinfo else item.starts_at.replace(tzinfo=UTC),
            source=item.source,
        )
        for item in payload
    ]
    count = request.app.state.repository.replace_events(events)
    return {"count": count}


@router.get("/news/events")
async def list_news_events(request: Request) -> list[dict[str, object]]:
    events = request.app.state.repository.list_events()
    return [
        {
            "title": event.title,
            "currency": event.currency,
            "impact": event.impact,
            "starts_at": event.starts_at,
            "source": event.source,
        }
        for event in events
    ]


@router.post("/ai/train")
async def train_ai_model(payload: TrainModelRequest, request: Request) -> dict[str, object]:
    model = request.app.state.engine.model
    if payload.rows:
        frame = pd.DataFrame(payload.rows)
    else:
        frame = model.sample_training_frame()
    model.train(frame)
    return {"trained": True, "rows": len(frame)}
