"""
AI Trading Platform – FastAPI Application.

Production-grade entry point wiring together:
  - Bot control (start / stop / pause / resume)
  - Trade monitoring and history
  - Signal feed with AI scores
  - Performance analytics
  - Dashboard endpoints for frontend
  - Backtesting engine
  - AI training pipeline
  - Monitoring, health, metrics
  - Prometheus instrumentation
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Centralised logging must be imported first so all modules inherit the config
from app.utils.logging_config import get_structured_logger, configure_logging
from app.config import settings
from app.database import create_tables
from app.monitoring.metrics import get_metrics

# Routes
from app.api.routes import control, trades, signals, performance
from app.api.routes import dashboard, monitoring, backtesting, training

from app.bot.trading_bot import get_bot
from app.core.ai.model_registry import ModelRegistry

logger = get_structured_logger("main")

# ── Prometheus instruments ────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["endpoint"],
)


# ── Lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown orchestration."""

    logger.info(f"{'='*60}")
    logger.info(f"  {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"  Mode: {settings.TRADING_MODE.value.upper()}")
    logger.info(f"{'='*60}")

    # Database
    try:
        await create_tables()
        logger.info("Database tables verified / created")
    except Exception as e:
        logger.error(f"Database init error: {e}")

    # Model registry + watcher
    try:
        registry = ModelRegistry()
        registry.start_watcher(poll_interval=60.0)
        logger.info(f"Model registry ready (version={registry.active_version})")
    except Exception as e:
        logger.warning(f"Model registry warning: {e}")

    # Auto-start bot
    auto_start = os.getenv("BOT_AUTO_START", "true").lower() == "true"
    bot = get_bot()
    if auto_start:
        try:
            asyncio.create_task(bot.start())
            logger.info("Bot auto-start initiated")
        except Exception as e:
            logger.error(f"Bot auto-start failed: {e}")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("Shutting down trading platform...")
    try:
        await bot.stop()
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")

    registry = ModelRegistry()
    registry.stop_watcher()
    logger.info("Shutdown complete")


# ── Application ───────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="""
## AI Trading Platform

Professional-grade automated trading system combining Smart Money Concepts,
multi-timeframe analysis, and a RandomForest AI classifier.

### Modules
| Module | Description |
|--------|-------------|
| **Bot Control** | Start / stop / pause / resume the engine |
| **Trades** | Real-time open positions + closed trade history |
| **Signals** | AI-scored trade signals with full SMC context |
| **Dashboard** | Equity curve, session heatmap, symbol analytics |
| **Backtesting** | Bar-by-bar simulation with spread + slippage |
| **AI Training** | Dataset builder → train → calibrate → hot-swap |
| **Monitoring** | Health, Prometheus metrics, performance tracker |

### Strategy: Sweep → BOS → Pullback (SMC)
1. Detect liquidity sweep (equal highs/lows hunters)
2. Confirm Break of Structure (CHoCH / BOS)
3. Enter on pullback into FVG / Order Block / 50% retracement

### Docs
- Swagger UI: `/docs`
- ReDoc: `/redoc`
- Prometheus metrics: `/metrics`
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    endpoint = request.url.path
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code,
    ).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    return response


# ── Routes ─────────────────────────────────────────────────────────────────

_v1 = "/api/v1"

app.include_router(control.router,     prefix=_v1)
app.include_router(trades.router,      prefix=_v1)
app.include_router(signals.router,     prefix=_v1)
app.include_router(performance.router, prefix=_v1)
app.include_router(dashboard.router,   prefix=_v1)
app.include_router(monitoring.router,  prefix=_v1)
app.include_router(backtesting.router, prefix=_v1)
app.include_router(training.router,    prefix=_v1)


# ── Core Endpoints ─────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    """Platform overview."""
    bot = get_bot()
    registry = ModelRegistry()
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "trading_mode": settings.TRADING_MODE.value,
        "bot_state": bot.state,
        "model_version": registry.active_version,
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health():
    """Kubernetes / Docker liveness probe."""
    return {
        "status": "healthy",
        "mode": settings.TRADING_MODE.value,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }


@app.get("/status", tags=["Health"])
async def status():
    """Detailed status (readiness probe)."""
    bot = get_bot()
    return bot.get_status()


@app.get("/metrics", tags=["Monitoring"])
async def prometheus_metrics():
    """Prometheus scrape endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Exception Handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    metrics = get_metrics()
    metrics.record_error("http_unhandled")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )
