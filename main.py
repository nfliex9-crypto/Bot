"""
AI Automated Trading Bot — Main Entry Point

Starts the FastAPI server and the background trading engine.
Supports paper and live trading modes.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn
from loguru import logger

from app.api.app import create_app
from app.api.routes import set_bot_reference
from app.bot import TradingBot
from app.core.config import settings
from app.core.database import Base, async_engine


async def init_database() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")


async def startup() -> None:
    await init_database()

    bot = TradingBot()
    await bot.initialize()
    set_bot_reference(bot)
    bot.start()

    logger.info(
        f"Bot is live — mode={settings.trading_mode.value} "
        f"balance=${settings.account_balance:.2f} "
        f"risk={settings.risk_per_trade}% "
        f"max_dd={settings.max_drawdown_pct}%"
    )
    return bot


def main() -> None:
    app = create_app()
    bot_ref = None

    @app.on_event("startup")
    async def on_startup():
        nonlocal bot_ref
        bot_ref = await startup()

    @app.on_event("shutdown")
    async def on_shutdown():
        if bot_ref:
            await bot_ref.stop()
        logger.info("Shutdown complete")

    logger.info(
        f"Starting AI Trading Bot on {settings.api_host}:{settings.api_port}"
    )

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
