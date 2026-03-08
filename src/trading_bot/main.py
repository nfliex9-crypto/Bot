from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .schemas import BotStatusResponse, RunOnceResponse, SignalResponse, TradeResponse
from .service import TradingBotService

settings = Settings()
service = TradingBotService(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await service.initialize()
    yield
    await service.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status", response_model=BotStatusResponse)
def status() -> BotStatusResponse:
    state = service.get_status()
    return BotStatusResponse(
        running=state.running,
        mode=state.mode,
        active_session=state.active_session,
        last_cycle_at=state.last_cycle_at,
        daily_drawdown=state.daily_drawdown,
        open_positions=state.open_positions,
    )


@app.post("/bot/start", response_model=BotStatusResponse)
async def start_bot() -> BotStatusResponse:
    await service.start()
    return status()


@app.post("/bot/stop", response_model=BotStatusResponse)
async def stop_bot() -> BotStatusResponse:
    await service.stop()
    return status()


@app.post("/bot/run-once", response_model=RunOnceResponse)
async def run_once() -> RunOnceResponse:
    result = await service.run_once()
    return RunOnceResponse(**result)


@app.get("/trades", response_model=list[TradeResponse])
def trades(limit: int = 20) -> list[TradeResponse]:
    return [
        TradeResponse(
            id=trade.id,
            symbol=trade.symbol,
            market=trade.market,
            direction=trade.direction,
            status=trade.status,
            mode=trade.mode,
            session=trade.session,
            entry_price=trade.entry_price,
            stop_loss=trade.stop_loss,
            take_profit_levels=trade.take_profit_levels,
            quantity=trade.quantity,
            remaining_quantity=trade.remaining_quantity,
            risk_amount=trade.risk_amount,
            confidence=trade.confidence,
            realized_pnl=trade.realized_pnl,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
        )
        for trade in service.list_trades(limit=limit)
    ]


@app.get("/signals", response_model=list[SignalResponse])
def signals(limit: int = 20) -> list[SignalResponse]:
    return [
        SignalResponse(
            id=signal.id,
            symbol=signal.symbol,
            market=signal.market,
            direction=signal.direction,
            reason=signal.reason,
            h1_bias=signal.h1_bias,
            m15_trend=signal.m15_trend,
            session=signal.session,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_levels=signal.take_profit_levels,
            atr=signal.atr,
            confidence=signal.confidence,
            created_at=signal.created_at,
        )
        for signal in service.list_signals(limit=limit)
    ]
