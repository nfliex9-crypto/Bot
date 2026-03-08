from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import EngineStatusResponse, SignalResponse, StartEngineRequest
from app.config import get_settings
from app.core.database import SessionLocal, get_db_session, init_db
from app.core.logging import configure_logging
from app.models.entities import TradeSignal
from app.trading.engine import TradingEngine

settings = get_settings()
configure_logging(settings.log_level)
engine = TradingEngine(settings=settings, session_factory=SessionLocal)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    if settings.auto_start_engine:
        await engine.start(mode=settings.mode)
    yield
    if engine.running:
        await engine.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(tz=timezone.utc).isoformat()}


@app.post("/engine/start")
async def start_engine(payload: StartEngineRequest) -> dict[str, str]:
    await engine.start(mode=payload.mode)
    return {"status": "started", "mode": payload.mode}


@app.post("/engine/stop")
async def stop_engine() -> dict[str, str]:
    await engine.stop()
    return {"status": "stopped"}


@app.get("/engine/status", response_model=EngineStatusResponse)
async def engine_status() -> EngineStatusResponse:
    return EngineStatusResponse(
        running=engine.running,
        mode=engine.mode,  # type: ignore[arg-type]
        active_positions=engine.position_manager.active_count(),
        trades_today=await engine.trades_today(),
        last_cycle_at=engine.last_cycle_at,
    )


@app.get("/signals/latest", response_model=list[SignalResponse])
async def latest_signals(
    limit: int = 20,
    db: AsyncSession = Depends(get_db_session),
) -> list[SignalResponse]:
    stmt = select(TradeSignal).order_by(desc(TradeSignal.created_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        SignalResponse(
            symbol=row.symbol,
            market=row.market,
            side=row.side,
            confidence=row.confidence,
            created_at=row.created_at,
        )
        for row in rows
    ]
