"""
AI Automated Trading System - FastAPI Application Entry Point

Startup sequence:
1. Initialize database tables
2. Bootstrap AI classifier
3. Connect to MT5 and Binance
4. Start background scheduler (signal scanning + monitoring)
5. Serve HTTP + WebSocket endpoints
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.api.v1 import api_router
from app.api.v1.websocket import websocket_endpoint, manager as ws_manager

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_signal_scan():
    """Scheduled task: scan all markets for trading signals."""
    async with AsyncSessionLocal() as db:
        from app.services.trade_manager import TradeManager
        try:
            tm = TradeManager(db)
            tm.set_broadcast_callback(
                lambda signal: ws_manager.broadcast({
                    "type": "signal",
                    "data": signal,
                })
            )
            await tm.initialize()
            signals = await tm.scan_and_generate_signals()
            if signals:
                logger.info(f"Scan complete: {len(signals)} signal(s) found")
        except Exception as e:
            logger.error(f"Signal scan error: {e}", exc_info=True)


async def run_trade_monitor():
    """Scheduled task: monitor open positions."""
    async with AsyncSessionLocal() as db:
        from app.services.trade_manager import TradeManager
        try:
            tm = TradeManager(db)
            await tm.initialize()
            await tm.monitor_open_trades()
        except Exception as e:
            logger.error(f"Trade monitor error: {e}", exc_info=True)


async def run_equity_snapshot():
    """Scheduled task: record equity snapshots."""
    async with AsyncSessionLocal() as db:
        from app.services.trade_manager import TradeManager
        try:
            tm = TradeManager(db)
            await tm.snapshot_equity()
        except Exception as e:
            logger.error(f"Equity snapshot error: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("=== AI Trading System Starting ===")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Bootstrap AI model
    from app.ai.classifier import TradingClassifier
    clf = TradingClassifier(model_path=settings.MODEL_PATH)
    logger.info(f"AI Classifier ready | Trained: {clf.is_trained}")

    # Schedule jobs
    scheduler.add_job(
        run_signal_scan,
        trigger=IntervalTrigger(minutes=5),
        id="signal_scan",
        name="Market Signal Scanner",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_trade_monitor,
        trigger=IntervalTrigger(seconds=30),
        id="trade_monitor",
        name="Open Trade Monitor",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_equity_snapshot,
        trigger=IntervalTrigger(minutes=15),
        id="equity_snapshot",
        name="Equity Snapshot",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started (scan every 5min, monitor every 30s)")

    # Run initial scan on startup
    asyncio.create_task(run_signal_scan())

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("=== AI Trading System Stopped ===")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered automated trading system for Forex and Crypto",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST API routes
app.include_router(api_router)


# WebSocket endpoint
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "ws_connections": ws_manager.connection_count,
        "scheduler_running": scheduler.running,
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
