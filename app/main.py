from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import desc

from app.config import Settings, get_settings
from app.core.logger import configure_logging
from app.db.init_db import init_db
from app.db.models import Trade
from app.db.session import SessionLocal
from app.schemas.api import BotControlRequest, BotStatusResponse, HealthResponse
from app.services.bot_service import BotService

settings: Settings = get_settings()
configure_logging(settings.log_level)
init_db()

app = FastAPI(
    title="AI Automated Trading Bot",
    version="1.0.0",
    description="24/7 multi-market trading bot (Forex MT5 + Crypto Binance) with AI confidence scoring.",
)
bot = BotService(settings)
scheduler = AsyncIOScheduler(timezone="UTC")


def _trade_to_dict(trade: Trade) -> dict:
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "market_type": trade.market_type,
        "side": trade.side,
        "mode": trade.mode,
        "status": trade.status,
        "confidence": trade.confidence,
        "entry_price": trade.entry_price,
        "stop_loss": trade.stop_loss,
        "tp1": trade.tp1,
        "tp2": trade.tp2,
        "tp3": trade.tp3,
        "position_size": trade.position_size,
        "risk_amount": trade.risk_amount,
        "tp1_hit": trade.tp1_hit,
        "tp2_hit": trade.tp2_hit,
        "tp3_hit": trade.tp3_hit,
        "opened_at": trade.opened_at.isoformat() if trade.opened_at else None,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        "execution_payload": trade.execution_payload,
        "metadata_json": trade.metadata_json,
    }


def scheduled_cycle() -> None:
    bot.run_cycle()


@app.on_event("startup")
async def startup_event():
    if not scheduler.running:
        scheduler.add_job(scheduled_cycle, "interval", seconds=settings.polling_seconds, id="bot-cycle", replace_existing=True)
        scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        mode=settings.trading_mode,
        running=bot.running,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/bot/status", response_model=BotStatusResponse)
def bot_status():
    return BotStatusResponse(**bot.status())


@app.post("/bot/control")
def bot_control(payload: BotControlRequest):
    bot.set_running(payload.running)
    return JSONResponse({"running": bot.running, "mode": settings.trading_mode})


@app.post("/bot/run-once")
def run_once():
    notes = bot.run_cycle()
    return {"ran": True, "notes": notes}


@app.get("/trades/open")
def open_trades():
    db = SessionLocal()
    try:
        rows = db.query(Trade).filter(Trade.status == "open").order_by(desc(Trade.id)).all()
        return {"count": len(rows), "trades": [_trade_to_dict(trade) for trade in rows]}
    finally:
        db.close()


@app.get("/trades/history")
def trade_history(limit: int = 50):
    db = SessionLocal()
    try:
        rows = db.query(Trade).order_by(desc(Trade.id)).limit(limit).all()
        return {"count": len(rows), "trades": [_trade_to_dict(trade) for trade in rows]}
    finally:
        db.close()

