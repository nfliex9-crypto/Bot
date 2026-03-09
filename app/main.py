"""
AI Trading Bot - FastAPI Application.

Entry point for the FastAPI web server that provides:
- Bot control API (start/stop/pause/resume)
- Trade monitoring and history
- Signal dashboard
- Performance analytics
- Real-time status
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from app.config import settings
from app.database import create_tables
from app.api.routes import control, trades, signals, performance, discovery
from app.bot.trading_bot import get_bot
from app.utils.logger import get_logger

logger = get_logger("main")

# Prometheus metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "Request duration", ["endpoint"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")

    # Create database tables
    try:
        await create_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

    # Auto-start bot if configured
    auto_start = os.getenv("BOT_AUTO_START", "true").lower() == "true"
    bot = get_bot()

    if auto_start:
        try:
            asyncio.create_task(bot.start())
            logger.info("Bot auto-start initiated")
        except Exception as e:
            logger.error(f"Bot auto-start failed: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        await bot.stop()
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")

    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="""
## AI Automated Trading Bot

Professional algorithmic trading system for Forex (MT5) and Crypto (Binance).

### Strategy
- **Liquidity Sweep** detection
- **Break of Structure** confirmation
- **Pullback Entry** in key zones (FVG, OB, 50% retracement)

### Multi-Timeframe Analysis
- H1: Market bias
- M15: Trend structure
- M5: Execution

### AI Layer
- RandomForest classifier
- Trade confidence scoring (threshold: {MIN_CONFIDENCE})

### Risk Management
- 0.75% risk per trade
- 15% max drawdown
- 3 max trades per session
- ATR & Structure stop loss
- TP1 (1R), TP2 (1.5R), TP3 (2R)
- Break-even after TP1
    """.format(MIN_CONFIDENCE=settings.MIN_CONFIDENCE),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Middleware ---

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    return response


# --- Routes ---

app.include_router(control.router, prefix="/api/v1")
app.include_router(trades.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(performance.router, prefix="/api/v1")
app.include_router(discovery.router, prefix="/api/v1")


@app.get("/", tags=["Root"])
async def root():
    """Bot status overview."""
    bot = get_bot()
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "trading_mode": settings.TRADING_MODE.value,
        "status": bot.get_status(),
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint (for Docker/K8s)."""
    return {"status": "healthy", "mode": settings.TRADING_MODE.value}


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )
