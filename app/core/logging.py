from __future__ import annotations

import sys

from loguru import logger

logger.remove()

logger.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    level="INFO",
    colorize=True,
)

logger.add(
    "logs/trading_bot_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    compression="gz",
    level="DEBUG",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
        "{level: <8} | "
        "{name}:{function}:{line} - {message}"
    ),
)

logger.add(
    "logs/trades_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="90 days",
    level="INFO",
    filter=lambda record: "trade" in record["extra"],
    format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
)
