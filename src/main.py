"""
Entry point for the AI Trading Bot.
Starts the bot orchestrator and optionally the API server.

Usage:
  python -m src.main              # Run bot only
  python -m src.main --with-api   # Run bot + API server
"""

import asyncio
import sys
import signal
from loguru import logger

from config.logging_config import setup_logging
from config.settings import settings
from src.bot.orchestrator import BotOrchestrator


def handle_shutdown(bot: BotOrchestrator):
    """Graceful shutdown handler for SIGTERM/SIGINT."""
    async def _stop():
        logger.warning("Shutdown signal received")
        await bot.stop()
        sys.exit(0)
    asyncio.create_task(_stop())


async def run_bot_with_api() -> None:
    """Run the trading bot alongside the FastAPI server."""
    import uvicorn
    from src.api.main import app
    from src.api.routes.bot_control import set_bot_state
    from datetime import datetime, timezone

    bot = BotOrchestrator()
    set_bot_state({"running": True, "start_time": datetime.now(tz=timezone.utc)})

    # Register shutdown handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: handle_shutdown(bot))

    config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        bot.start(),
        server.serve(),
    )


async def run_bot_only() -> None:
    """Run only the trading bot without the API server."""
    bot = BotOrchestrator()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: handle_shutdown(bot))

    await bot.start()


def main() -> None:
    setup_logging()

    logger.info("=" * 60)
    logger.info("  AI TRADING BOT")
    logger.info(f"  Mode: {settings.trading_mode.value.upper()}")
    logger.info(f"  Balance: ${settings.account_balance:,.2f}")
    logger.info(f"  Risk/Trade: {settings.risk_per_trade:.2%}")
    logger.info(f"  Max Drawdown: {settings.max_drawdown_pct:.2%}")
    logger.info(f"  Forex Symbols: {settings.mt5_symbol_list}")
    logger.info(f"  Crypto Symbols: {settings.binance_symbol_list}")
    logger.info("=" * 60)

    with_api = "--with-api" in sys.argv

    if with_api:
        asyncio.run(run_bot_with_api())
    else:
        asyncio.run(run_bot_only())


if __name__ == "__main__":
    main()
