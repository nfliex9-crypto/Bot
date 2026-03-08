from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import control, dashboard, trades
from api.routes.control import register_engine
from config.settings import settings
from database.connection import close_db, init_db
from utils.logger import get_logger

logger = get_logger(__name__)

_engine_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine_task
    logger.info("=== AI Trading Bot starting up ===")

    # Initialise database
    await init_db()

    # Create and start the trading engine in a background task
    from core.engine import TradingEngine
    engine = TradingEngine()
    register_engine(engine)
    app.state.engine = engine
    _engine_task = asyncio.create_task(engine.start(), name="trading_engine")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("=== AI Trading Bot shutting down ===")
    if _engine_task and not _engine_task.done():
        await app.state.engine.stop()
        _engine_task.cancel()
        try:
            await _engine_task
        except asyncio.CancelledError:
            pass
    await close_db()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Trading Bot",
        description=(
            "Professional AI-powered automated trading bot for Forex (MT5) and Crypto (Binance). "
            "Strategy: Liquidity Sweep + Break of Structure + Pullback Entry with RandomForest AI confidence scoring."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request timing middleware ──────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        process_time = (time.perf_counter() - start) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
        return response

    # ── Global error handler ──────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc)},
        )

    # ── Routes ────────────────────────────────────────────────
    app.include_router(control.router)
    app.include_router(dashboard.router)
    app.include_router(trades.router)

    # ── Health check ──────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    async def health():
        return {
            "status": "ok",
            "mode": settings.trading_mode,
            "version": "1.0.0",
        }

    @app.get("/", tags=["Health"])
    async def root():
        return {
            "name": "AI Trading Bot",
            "version": "1.0.0",
            "docs": "/docs",
            "mode": settings.trading_mode,
            "status": "running",
        }

    return app


app = create_app()
