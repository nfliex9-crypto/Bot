from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional

from src.api.schemas import BotStatusResponse, BotControlRequest, HealthResponse
from src.filters.session_filter import SessionFilter
from config.settings import settings

router = APIRouter(prefix="/bot", tags=["Bot Control"])

# Reference to the global bot state (injected at startup)
_bot_state: dict = {
    "running": False,
    "paused": False,
    "start_time": None,
    "last_scan": None,
    "active_symbols": [],
}

session_filter = SessionFilter()


def get_bot_state() -> dict:
    return _bot_state


def set_bot_state(state: dict) -> None:
    _bot_state.update(state)


@router.get("/status", response_model=BotStatusResponse)
async def get_bot_status():
    """Get current bot status and health."""
    from src.bot.orchestrator import get_orchestrator_status
    try:
        orch_status = get_orchestrator_status()
    except Exception:
        orch_status = {}

    uptime = 0.0
    if _bot_state["start_time"]:
        uptime = (datetime.now(tz=timezone.utc) - _bot_state["start_time"]).total_seconds()

    session_info = session_filter.get_session_info()

    return BotStatusResponse(
        running=_bot_state["running"],
        mode=settings.trading_mode.value,
        uptime_seconds=uptime,
        last_scan=_bot_state.get("last_scan"),
        active_symbols=_bot_state.get("active_symbols", []),
        session_info=session_info,
        ai_status=orch_status.get("ai_status", {}),
        risk_status=orch_status.get("risk_status", {}),
    )


@router.post("/control")
async def control_bot(request: BotControlRequest):
    """Control bot operation: start | stop | pause | resume | retrain_ai"""
    from src.bot.orchestrator import get_orchestrator

    action = request.action.lower()
    orch = get_orchestrator()

    if action == "stop":
        if orch:
            await orch.stop()
        _bot_state["running"] = False
        return {"status": "stopped"}

    elif action == "pause":
        if orch:
            orch.pause()
        _bot_state["paused"] = True
        return {"status": "paused"}

    elif action == "resume":
        if orch:
            orch.resume()
        _bot_state["paused"] = False
        return {"status": "resumed"}

    elif action == "retrain_ai":
        if orch:
            result = await orch.retrain_ai()
            return {"status": "retrained", "result": result}
        return {"status": "error", "message": "Orchestrator not running"}

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.now(tz=timezone.utc),
        database="connected",
        trading_mode=settings.trading_mode.value,
    )


@router.get("/session")
async def get_session_info():
    """Get current trading session information."""
    return session_filter.get_session_info()
