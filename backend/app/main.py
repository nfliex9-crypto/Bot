from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.api import auth, trading, ai, equity, websocket
from app.services.trading_service import get_execution_engine

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Trading System", environment=settings.environment)
    engine = get_execution_engine()
    status = await engine.initialize()
    logger.info("Engine initialized", status=status)
    yield
    await engine.shutdown()
    logger.info("AI Trading System shutdown complete")


app = FastAPI(
    title="AI Automated Trading System",
    description="Full AI-powered trading system with liquidity sweep detection, "
                "break of structure analysis, and pullback entry models.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(trading.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(equity.router, prefix="/api/v1")
app.include_router(websocket.router)


@app.get("/health")
async def health_check():
    engine = get_execution_engine()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "connections": {
            "mt5": engine.mt5._connected,
            "binance": engine.binance._connected,
        },
    }


@app.get("/")
async def root():
    return {
        "name": "AI Automated Trading System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
