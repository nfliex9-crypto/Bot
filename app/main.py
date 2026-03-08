from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select

from app.config import get_settings
from app.container import build_engine
from app.db import get_db_session, init_db
from app.models import AccountSnapshot, Trade
from app.schemas import StatusResponse, TradeResponse, TrainResponse
from app.logger import setup_logging

settings = get_settings()
setup_logging(settings.log_level)

engine = build_engine(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()


app = FastAPI(title="AI Trading Bot", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": settings.trading_mode}


@app.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    with get_db_session() as session:
        open_trades = session.scalar(select(func.count(Trade.id)).where(Trade.status == "open")) or 0
        latest = session.execute(
            select(AccountSnapshot).order_by(AccountSnapshot.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        equity = latest.equity if latest else settings.account_balance
        drawdown = latest.drawdown if latest else 0.0
    return StatusResponse(
        running=engine.running,
        mode=settings.trading_mode,
        open_trades=int(open_trades),
        latest_equity=float(equity),
        latest_drawdown=float(drawdown),
        symbols={"forex": settings.forex_symbols, "crypto": settings.crypto_symbols},
    )


@app.post("/bot/start")
async def start_bot() -> dict:
    if engine.running:
        return {"running": True, "message": "Already running."}
    await engine.start()
    return {"running": True, "message": "Bot started."}


@app.post("/bot/stop")
async def stop_bot() -> dict:
    await engine.stop()
    return {"running": False, "message": "Bot stopped."}


@app.post("/bot/run-once")
async def run_once() -> dict:
    await engine.run_once()
    return {"message": "Cycle completed."}


@app.post("/ai/train", response_model=TrainResponse)
def train_model() -> TrainResponse:
    with get_db_session() as session:
        return engine.ai_service.train_from_db(session)


@app.get("/trades", response_model=list[TradeResponse])
def list_trades(status: Optional[str] = Query(default=None)) -> list[TradeResponse]:
    with get_db_session() as session:
        query = select(Trade).order_by(Trade.created_at.desc()).limit(200)
        if status:
            query = query.where(Trade.status == status)
        trades = session.execute(query).scalars().all()
        return [TradeResponse.model_validate(t) for t in trades]


@app.get("/trades/{trade_id}", response_model=TradeResponse)
def get_trade(trade_id: int) -> TradeResponse:
    with get_db_session() as session:
        trade = session.execute(select(Trade).where(Trade.id == trade_id)).scalar_one_or_none()
        if trade is None:
            raise HTTPException(status_code=404, detail="Trade not found")
        return TradeResponse.model_validate(trade)

