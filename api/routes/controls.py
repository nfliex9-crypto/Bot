from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/controls", tags=["controls"])

_engine_ref = None


def set_engine_ref(engine) -> None:
    global _engine_ref
    _engine_ref = engine


class ActionResponse(BaseModel):
    success: bool
    message: str


@router.get("/status")
async def get_status():
    if _engine_ref is None:
        raise HTTPException(503, "Engine not initialized")
    return _engine_ref.get_status()


@router.post("/stop", response_model=ActionResponse)
async def stop_engine():
    if _engine_ref is None:
        raise HTTPException(503, "Engine not initialized")
    await _engine_ref.stop()
    return ActionResponse(success=True, message="Engine stop requested")


@router.post("/close-all", response_model=ActionResponse)
async def close_all_trades():
    if _engine_ref is None:
        raise HTTPException(503, "Engine not initialized")
    forex_closed = 0
    crypto_closed = 0
    if _engine_ref._forex_tm:
        forex_closed = await _engine_ref._forex_tm.close_all("api_close_all")
    if _engine_ref._crypto_tm:
        crypto_closed = await _engine_ref._crypto_tm.close_all("api_close_all")
    return ActionResponse(
        success=True,
        message=f"Closed {forex_closed} forex and {crypto_closed} crypto trades",
    )
