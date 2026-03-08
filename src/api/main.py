"""
FastAPI application for the AI Trading Bot.
Provides REST API for monitoring and controlling the bot.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routes.trades import router as trades_router
from src.api.routes.performance import router as performance_router
from src.api.routes.bot_control import router as bot_control_router, set_bot_state
from src.models.database import init_db
from config.logging_config import setup_logging
from config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    setup_logging()
    logger.info("Starting AI Trading Bot API")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")

    set_bot_state({
        "running": False,
        "start_time": datetime.now(tz=timezone.utc),
    })

    yield

    logger.info("API shutting down")


app = FastAPI(
    title="AI Trading Bot",
    description=(
        "Professional AI-powered automated trading system for Forex (MT5) and Crypto (Binance). "
        "Strategy: Liquidity Sweep + Break of Structure + Pullback Entry with RandomForest AI scoring."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "mode": settings.trading_mode.value,
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "name": "AI Trading Bot",
        "version": "1.0.0",
        "docs": "/docs",
        "mode": settings.trading_mode.value,
    }


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(trades_router, prefix="/api/v1")
app.include_router(performance_router, prefix="/api/v1")
app.include_router(bot_control_router, prefix="/api/v1")
