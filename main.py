#!/usr/bin/env python3
"""
AI Automated Trading Bot — Entry Point

Runs the trading engine alongside the FastAPI dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

from api.main import create_app
from api.routes.controls import set_engine_ref
from bot.engine import TradingEngine
from config.settings import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
LOG_DATE = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    log_dir = Path(settings.base_dir) / "logs"
    log_dir.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE))
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "trading_bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE))
    root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


import logging.handlers  # noqa: E402 — needed for RotatingFileHandler


async def run_api(app) -> None:
    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    engine = TradingEngine()
    set_engine_ref(engine)
    app = create_app()

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_signal(sig, frame):
        logger.info("Received signal %s — shutting down", sig)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    engine_task = asyncio.create_task(engine.start())
    api_task = asyncio.create_task(run_api(app))

    logger.info("API dashboard: http://%s:%d", settings.api_host, settings.api_port)

    done, pending = await asyncio.wait(
        [engine_task, api_task, asyncio.create_task(stop_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    await engine.stop()

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
