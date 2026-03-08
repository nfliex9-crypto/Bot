"""
Entry point for the AI Trading Bot.

Starts the FastAPI server and the bot's main loop concurrently.
The bot runs as a background task inside the same async event loop.
"""

from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn

from api.app import create_app
from bot import TradingBot
from config.settings import get_config
from core.logger import setup_logger

config = get_config()
logger = setup_logger(level=config.log_level)
app = create_app()
bot = TradingBot(config)


@app.on_event("startup")
async def startup():
    asyncio.create_task(bot.start())
    logger.info(f"API server starting on {config.api_host}:{config.api_port}")


@app.on_event("shutdown")
async def shutdown():
    await bot.stop()
    logger.info("Shutdown complete")


def main():
    logger.info("=" * 60)
    logger.info("  AI TRADING BOT — SMC Strategy + RandomForest Classifier")
    logger.info(f"  Mode: {config.mode.value.upper()}")
    logger.info(f"  Balance: ${config.risk.account_balance:.2f}")
    logger.info(f"  Risk/Trade: {config.risk.risk_per_trade:.2%}")
    logger.info(f"  Max Drawdown: {config.risk.max_drawdown:.2%}")
    logger.info(f"  Max Trades/Session: {config.risk.max_trades_per_session}")
    logger.info(f"  Forex Symbols: {config.forex_symbols}")
    logger.info(f"  Crypto Symbols: {config.crypto_symbols}")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        log_level=config.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
