"""
FastAPI routes for the trading bot dashboard and control API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.logger import get_logger

logger = get_logger("api")
router = APIRouter()

_bot_ref = None


def set_bot_reference(bot):
    """Inject the bot instance so routes can access it."""
    global _bot_ref
    _bot_ref = bot


class StatusResponse(BaseModel):
    status: str
    mode: str
    uptime: str
    active_sessions: list
    risk_summary: dict
    open_trades: int
    timestamp: str


class TradeResponse(BaseModel):
    trades: list
    count: int


class SignalResponse(BaseModel):
    signals: list
    count: int


class ModeRequest(BaseModel):
    mode: str  # "paper" or "live"


class ManualSignalRequest(BaseModel):
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: Optional[float] = None
    tp3: Optional[float] = None


@router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/status", response_model=StatusResponse)
async def get_status():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    bot = _bot_ref
    uptime = str(datetime.utcnow() - bot.start_time) if bot.start_time else "N/A"
    sessions = bot.session_filter.get_active_sessions() if bot.session_filter else []

    return StatusResponse(
        status="running" if bot.running else "stopped",
        mode=bot.config.mode.value,
        uptime=uptime,
        active_sessions=sessions,
        risk_summary=bot.risk_manager.get_risk_summary(),
        open_trades=len(bot.risk_manager.open_trades),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/trades", response_model=TradeResponse)
async def get_trades():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    trades = _bot_ref.db.get_recent_trades(50)
    return TradeResponse(trades=trades, count=len(trades))


@router.get("/trades/open")
async def get_open_trades():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    open_trades = [
        {
            "trade_id": t.trade_id,
            "symbol": t.symbol,
            "direction": t.direction.value,
            "entry_price": t.entry_price,
            "current_price": t.current_price,
            "stop_loss": t.stop_loss,
            "tp1": t.tp1, "tp2": t.tp2, "tp3": t.tp3,
            "pnl": t.pnl,
            "tp1_hit": t.tp1_hit,
            "breakeven_set": t.breakeven_set,
        }
        for t in _bot_ref.risk_manager.open_trades
    ]
    return {"trades": open_trades, "count": len(open_trades)}


@router.get("/account")
async def get_account():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return _bot_ref.risk_manager.get_risk_summary()


@router.get("/account/history")
async def get_account_history(days: int = 30):
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return _bot_ref.db.get_account_history(days)


@router.get("/signals/recent")
async def get_recent_signals():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return {"signals": _bot_ref.recent_signals[-20:], "count": len(_bot_ref.recent_signals)}


@router.post("/mode")
async def switch_mode(req: ModeRequest):
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    if req.mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="Mode must be 'paper' or 'live'")
    from config.settings import TradingMode
    _bot_ref.config.mode = TradingMode(req.mode)
    logger.info(f"Trading mode switched to {req.mode}")
    return {"status": "ok", "mode": req.mode}


@router.post("/bot/stop")
async def stop_bot():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    _bot_ref.running = False
    return {"status": "stopping"}


@router.post("/bot/start")
async def start_bot():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    if not _bot_ref.running:
        _bot_ref.running = True
    return {"status": "started"}


@router.get("/ml/status")
async def ml_status():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return {
        "model_trained": _bot_ref.classifier.is_trained,
        "feature_count": len(_bot_ref.classifier.feature_names),
    }


@router.post("/ml/retrain")
async def retrain_model():
    if not _bot_ref:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    features_df, labels = _bot_ref.db.get_ml_training_data()
    if features_df.empty:
        return {"status": "no_data"}
    result = _bot_ref.classifier.train(features_df, labels)
    return result
