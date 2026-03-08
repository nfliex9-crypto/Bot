"""
Bot Control API Routes.

Provides endpoints to start, stop, pause, resume, and monitor the trading bot.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.bot.trading_bot import get_bot, BotState
from app.config import settings

router = APIRouter(prefix="/bot", tags=["Bot Control"])


class BotConfigUpdate(BaseModel):
    trading_mode: Optional[str] = None
    risk_per_trade: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_trades_per_session: Optional[int] = None
    min_confidence: Optional[float] = None


@router.get("/status")
async def get_status():
    """Get current bot status and statistics."""
    bot = get_bot()
    return bot.get_status()


@router.post("/start")
async def start_bot(background_tasks: BackgroundTasks):
    """Start the trading bot."""
    bot = get_bot()
    if bot.state in (BotState.RUNNING, BotState.STARTING):
        raise HTTPException(status_code=400, detail="Bot is already running")

    background_tasks.add_task(bot.start)
    return {"message": "Bot starting...", "state": BotState.STARTING}


@router.post("/stop")
async def stop_bot():
    """Stop the trading bot."""
    bot = get_bot()
    if bot.state == BotState.STOPPED:
        raise HTTPException(status_code=400, detail="Bot is not running")

    await bot.stop()
    return {"message": "Bot stopped", "state": BotState.STOPPED}


@router.post("/pause")
async def pause_bot():
    """Pause the trading bot (stops new trades, keeps monitoring open positions)."""
    bot = get_bot()
    if bot.state != BotState.RUNNING:
        raise HTTPException(status_code=400, detail="Bot is not running")

    await bot.pause()
    return {"message": "Bot paused", "state": BotState.PAUSED}


@router.post("/resume")
async def resume_bot():
    """Resume a paused trading bot."""
    bot = get_bot()
    if bot.state != BotState.PAUSED:
        raise HTTPException(status_code=400, detail="Bot is not paused")

    await bot.resume()
    return {"message": "Bot resumed", "state": BotState.RUNNING}


@router.get("/config")
async def get_config():
    """Get current bot configuration."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "trading_mode": settings.TRADING_MODE.value,
        "risk_management": {
            "account_balance": settings.ACCOUNT_BALANCE,
            "risk_per_trade": settings.RISK_PER_TRADE,
            "risk_per_trade_pct": f"{settings.RISK_PER_TRADE * 100:.2f}%",
            "max_drawdown": settings.MAX_DRAWDOWN,
            "max_drawdown_pct": f"{settings.MAX_DRAWDOWN * 100:.1f}%",
            "max_trades_per_session": settings.MAX_TRADES_PER_SESSION,
        },
        "trade_management": {
            "tp1_ratio": settings.TP1_RATIO,
            "tp2_ratio": settings.TP2_RATIO,
            "tp3_ratio": settings.TP3_RATIO,
            "breakeven_after_tp1": settings.BREAKEVEN_AFTER_TP1,
        },
        "ai": {
            "min_confidence": settings.MIN_CONFIDENCE,
            "model_path": settings.MODEL_PATH,
        },
        "sessions": {
            "london": f"{settings.LONDON_OPEN_UTC:02d}:00-{settings.LONDON_CLOSE_UTC:02d}:00 UTC",
            "new_york": f"{settings.NEW_YORK_OPEN_UTC:02d}:00-{settings.NEW_YORK_CLOSE_UTC:02d}:00 UTC",
        },
        "symbols": {
            "forex": settings.forex_symbol_list,
            "crypto": settings.crypto_symbol_list,
        },
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    bot = get_bot()
    return {
        "status": "healthy",
        "bot_state": bot.state,
        "trading_mode": settings.TRADING_MODE.value,
    }


@router.post("/reset-session")
async def reset_session():
    """Reset session trade counter (use at start of each trading session)."""
    bot = get_bot()
    if bot.risk_manager:
        bot.risk_manager.reset_session()
    return {"message": "Session reset", "session_trades": 0}
