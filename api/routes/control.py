from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/control", tags=["Control"])

# The engine instance is injected from the app state
_engine_ref = None


def get_engine():
    if _engine_ref is None:
        raise HTTPException(status_code=503, detail="Trading engine not initialised")
    return _engine_ref


def register_engine(engine) -> None:
    global _engine_ref
    _engine_ref = engine


# ─── Request / Response Models ────────────────────────────────────────────────

class ModeRequest(BaseModel):
    mode: str   # "paper" | "live"


class StatusResponse(BaseModel):
    running: bool
    paused: bool
    mode: str
    cycle: int
    session: str
    account: dict
    errors: list


class MessageResponse(BaseModel):
    message: str
    success: bool


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status(engine=Depends(get_engine)):
    return engine.get_status()


@router.post("/pause", response_model=MessageResponse)
async def pause_engine(engine=Depends(get_engine)):
    if engine.is_paused:
        return MessageResponse(message="Engine already paused", success=False)
    engine.pause()
    return MessageResponse(message="Trading engine paused", success=True)


@router.post("/resume", response_model=MessageResponse)
async def resume_engine(engine=Depends(get_engine)):
    if not engine.is_paused:
        return MessageResponse(message="Engine is not paused", success=False)
    engine.resume()
    return MessageResponse(message="Trading engine resumed", success=True)


@router.get("/open-trades")
async def get_open_trades(engine=Depends(get_engine)):
    return engine.get_open_trades()


@router.get("/session")
async def get_session_info():
    from filters.session_filter import session_filter
    from filters.news_filter import news_filter
    current = session_filter.current_session()
    return {
        "current_session": current.value,
        "tradeable": session_filter.is_tradeable("EURUSD"),
        "minutes_to_next_session": session_filter.minutes_to_session_open(),
        "todays_news": news_filter.get_todays_events(),
    }


@router.post("/retrain-ai", response_model=MessageResponse)
async def retrain_ai_models(engine=Depends(get_engine)):
    """
    Trigger a background retraining of all AI classifiers.
    This is a non-blocking call — training happens in the background.
    """
    import asyncio
    from ai.classifier import classifier_registry
    from config.settings import settings
    from core.models import Direction

    async def _retrain():
        from core.data_feed import DataFeed
        from execution.mt5_executor import MT5Executor
        from execution.binance_executor import BinanceExecutor

        mt5_feed = DataFeed(engine._mt5)
        binance_feed = DataFeed(engine._binance)

        timeframes = [settings.bias_timeframe, settings.trend_timeframe, settings.entry_timeframe]
        await mt5_feed.initialise(settings.forex_symbol_list, timeframes)
        await binance_feed.initialise(settings.crypto_symbol_list, timeframes)

        for symbol in settings.forex_symbol_list + settings.crypto_symbol_list:
            feed = mt5_feed if symbol in settings.forex_symbol_list else binance_feed
            df = await feed.get(symbol, settings.entry_timeframe)
            if not df.empty:
                clf = classifier_registry.get(symbol)
                clf.train(df, Direction.LONG)

    asyncio.create_task(_retrain())
    return MessageResponse(message="AI retraining started in background", success=True)
