from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import init_db
from app.db.session import SessionLocal
from app.routers.dashboard import router as dashboard_router
from app.routers.health import router as health_router
from app.routers.signals import router as signals_router
from app.routers.trades import router as trades_router
from app.services.orchestrator import TradingOrchestrator

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)
orchestrator = TradingOrchestrator()


async def trading_loop() -> None:
    while True:
        db = SessionLocal()
        try:
            summary = orchestrator.run_cycle(db)
            logger.info("Trading cycle complete: %s", summary)
        except Exception:
            logger.exception("Trading cycle failed")
            db.rollback()
        finally:
            db.close()
        await asyncio.sleep(settings.loop_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    task: asyncio.Task | None = None
    if settings.enable_background_loop:
        task = asyncio.create_task(trading_loop())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title=settings.project_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(signals_router)
app.include_router(trades_router)
