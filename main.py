#!/usr/bin/env python3
"""
AI Trading Bot — Main Entrypoint

Starts the FastAPI server with the trading engine running as a
background task inside the same async event loop.

Usage:
    python main.py
    # or
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
"""
from __future__ import annotations

import os
import sys

import uvicorn

# Ensure project root is in path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api.app import app  # noqa: F401 — imported so uvicorn can find it
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    logger.info(
        "Launching AI Trading Bot | mode=%s | host=%s | port=%d",
        settings.trading_mode.upper(),
        settings.api_host,
        settings.api_port,
    )
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        workers=1,           # Single worker required — engine state must be shared
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
