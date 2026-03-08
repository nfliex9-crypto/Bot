"""
Structured logging for the trading bot.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "trading_bot", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(log_dir / f"bot_{today}.log")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    trade_handler = logging.FileHandler(log_dir / f"trades_{today}.log")
    trade_handler.setFormatter(fmt)
    trade_handler.setLevel(logging.INFO)
    trade_logger = logging.getLogger(f"{name}.trades")
    trade_logger.addHandler(trade_handler)

    return logger


def get_logger(module: str) -> logging.Logger:
    return logging.getLogger(f"trading_bot.{module}")
